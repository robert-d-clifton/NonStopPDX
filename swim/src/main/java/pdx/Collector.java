package pdx;

import com.solacesystems.jms.SupportedProperty;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.Hashtable;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.zip.GZIPInputStream;
import java.util.zip.GZIPOutputStream;

import javax.jms.BytesMessage;
import javax.jms.Connection;
import javax.jms.ConnectionFactory;
import javax.jms.Message;
import javax.jms.MessageConsumer;
import javax.jms.Session;
import javax.jms.TextMessage;
import javax.naming.Context;
import javax.naming.InitialContext;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NamedNodeMap;
import org.w3c.dom.NodeList;

/**
 * Reads the TFMS flight data feed from SWIM and keeps only airline flights to or from one airport.
 *
 * Each flight message whose departure or arrival airport matches, and whose operator is listed in
 * the operators file, is written as one line of XML to a gzip file per UTC day. Everything else,
 * including all private and charter flights, is dropped in memory and never written anywhere.
 * The log carries counts only, never call signs or registrations.
 */
public final class Collector {

    static final String AIRPORT = env("SWIM_AIRPORT", "KPDX");
    static final Path OUT = Path.of(env("SWIM_OUT", "/out"));
    static final Path OPERATORS = Path.of(env("SWIM_OPERATORS", "/config/operators.json"));
    static final Pattern CALL_SIGN = Pattern.compile("^([A-Z]{3})\\d");
    // Position reports: most of the volume, and nothing the site needs.
    static final Set<String> SKIP_TYPES = Set.of(env("SWIM_SKIP_TYPES", "trackInformation,boundaryCrossingUpdate").split("\\s*,\\s*"));

    final Set<String> operators;
    final DocumentBuilder parser;
    final Transformer printer;
    final Stats stats = new Stats();
    LocalDate day;
    OutputStream file;
    int unflushed;

    Collector(Set<String> operators) throws Exception {
        this.operators = operators;
        DocumentBuilderFactory f = DocumentBuilderFactory.newInstance();
        f.setNamespaceAware(true);
        f.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
        f.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        parser = f.newDocumentBuilder();
        printer = TransformerFactory.newInstance().newTransformer();
        printer.setOutputProperty(OutputKeys.OMIT_XML_DECLARATION, "yes");
        printer.setOutputProperty(OutputKeys.INDENT, "no");
    }

    public static void main(String[] args) throws Exception {
        Set<String> operators = readOperators();
        log("Keeping flights to or from " + AIRPORT + " by " + operators.size() + " airlines");
        Collector collector = new Collector(operators);

        Hashtable<String, Object> jndi = new Hashtable<>();
        jndi.put(Context.INITIAL_CONTEXT_FACTORY, "com.solacesystems.jndi.SolJNDIInitialContextFactory");
        jndi.put(Context.PROVIDER_URL, required("SWIM_URL"));
        jndi.put(Context.SECURITY_PRINCIPAL, required("SWIM_USERNAME"));
        jndi.put(Context.SECURITY_CREDENTIALS, required("SWIM_PASSWORD"));
        jndi.put(SupportedProperty.SOLACE_JMS_VPN, required("SWIM_VPN"));
        // The FAA terms require compressed delivery.
        jndi.put(SupportedProperty.SOLACE_JMS_COMPRESSION_LEVEL, 9);
        jndi.put(SupportedProperty.SOLACE_JMS_SSL_VALIDATE_CERTIFICATE, true);

        InitialContext context = new InitialContext(jndi);
        ConnectionFactory factory = (ConnectionFactory) context.lookup(required("SWIM_CONNECTION_FACTORY"));
        Connection connection = factory.createConnection();
        connection.setExceptionListener(e -> {
            // Let Docker restart the container rather than reconnecting by hand.
            log("Connection lost: " + e.getMessage());
            collector.close();
            System.exit(1);
        });
        Session session = connection.createSession(false, Session.AUTO_ACKNOWLEDGE);
        MessageConsumer consumer = session.createConsumer(session.createQueue(required("SWIM_QUEUE")));
        consumer.setMessageListener(collector::receive);

        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                connection.close();
            } catch (Exception ignored) {
            }
            collector.close();
            collector.stats.report();
        }));
        Executors.newSingleThreadScheduledExecutor()
                .scheduleAtFixedRate(collector.stats::report, 5, 60, TimeUnit.MINUTES);

        connection.start();
        log("Connected, waiting for messages");
        Thread.currentThread().join();
    }

    synchronized void receive(Message message) {
        try {
            Document doc = parser.parse(new ByteArrayInputStream(body(message, stats)));
            stats.message(doc.getDocumentElement().getLocalName());
            NodeList flights = doc.getElementsByTagNameNS("*", "fltdMessage");
            for (int i = 0; i < flights.getLength(); i++) {
                Element flight = (Element) flights.item(i);
                stats.flight(flight);
                if (!AIRPORT.equals(flight.getAttribute("depArpt")) && !AIRPORT.equals(flight.getAttribute("arrArpt"))) {
                    continue;
                }
                String operator = operator(flight);
                if (operator == null || !operators.contains(operator)) {
                    stats.dropped(operator);
                    continue;
                }
                // "A" is the FAA's mark for an ordinary, unrestricted flight; anything else is left out.
                String sensitivity = flight.getAttribute("sensitivity");
                if (!"A".equals(sensitivity)) {
                    stats.dropped("sensitivity " + (sensitivity.isEmpty() ? "missing" : sensitivity));
                    continue;
                }
                String type = flight.getAttribute("msgType");
                if (SKIP_TYPES.contains(type)) {
                    stats.skipped(type);
                    continue;
                }
                write(flight);
                stats.kept(flight.getAttribute("msgType"));
            }
        } catch (Exception e) {
            stats.error(e);
        }
    }

    /** The three letter airline code, from the airline attribute or the start of the call sign. */
    static String operator(Element flight) {
        String airline = flight.getAttribute("airline").trim().toUpperCase();
        if (airline.matches("[A-Z]{3}")) {
            return airline;
        }
        Matcher m = CALL_SIGN.matcher(flight.getAttribute("acid").trim().toUpperCase());
        return m.find() ? m.group(1) : null;
    }

    static byte[] body(Message message, Stats stats) throws Exception {
        byte[] bytes;
        if (message instanceof TextMessage text) {
            bytes = text.getText().getBytes(StandardCharsets.UTF_8);
        } else if (message instanceof BytesMessage raw) {
            bytes = new byte[(int) raw.getBodyLength()];
            raw.readBytes(bytes);
        } else {
            throw new IllegalArgumentException("unexpected message type " + message.getClass().getSimpleName());
        }
        boolean gzipped = bytes.length > 2 && (bytes[0] & 0xff) == 0x1f && (bytes[1] & 0xff) == 0x8b;
        stats.delivered(message instanceof TextMessage ? "text" : "bytes", gzipped, bytes.length);
        if (gzipped) {
            try (InputStream in = new GZIPInputStream(new ByteArrayInputStream(bytes))) {
                bytes = in.readAllBytes();
            }
        }
        stats.payload(bytes.length);
        return bytes;
    }

    void write(Element flight) throws Exception {
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        if (!today.equals(day)) {
            close();
            Path path = OUT.resolve("flights-" + today + ".xml.gz");
            // Appending a new gzip member keeps the file readable across restarts.
            file = new GZIPOutputStream(Files.newOutputStream(path, StandardOpenOption.CREATE, StandardOpenOption.APPEND), true);
            day = today;
        }
        StringWriter line = new StringWriter();
        printer.transform(new DOMSource(flight), new StreamResult(line));
        file.write(line.toString().replace("\r", "").replace("\n", " ").getBytes(StandardCharsets.UTF_8));
        file.write('\n');
        // Flushing every line ruins compression, so flush every so often; a crash loses at most a few minutes.
        if (++unflushed >= 200) {
            file.flush();
            unflushed = 0;
        }
    }

    synchronized void close() {
        if (file != null) {
            try {
                file.close();
            } catch (IOException e) {
                log("Couldn't close the day's file: " + e.getMessage());
            }
            file = null;
            day = null;
        }
    }

    static Set<String> readOperators() throws IOException {
        String json = Files.readString(OPERATORS);
        int start = json.indexOf("\"operators\"");
        Matcher m = Pattern.compile("\"([A-Z0-9]{3})\"\\s*:").matcher(json.substring(start));
        Set<String> codes = new java.util.TreeSet<>();
        while (m.find()) {
            codes.add(m.group(1));
        }
        if (codes.isEmpty()) {
            throw new IllegalStateException("No operators found in " + OPERATORS);
        }
        return codes;
    }

    static String env(String name, String fallback) {
        String value = System.getenv(name);
        return value == null || value.isBlank() ? fallback : value.trim();
    }

    static String required(String name) {
        String value = env(name, null);
        if (value == null) {
            log("Missing " + name + " in .env");
            System.exit(2);
        }
        return value;
    }

    static void log(String line) {
        System.out.println(Instant.now().toString().substring(0, 19) + "Z " + line);
    }

    /** Counts for the log. Holds airline codes and attribute names, never call signs. */
    static final class Stats {
        long messages, flights, kept, errors;
        final Map<String, Long> roots = new TreeMap<>();
        final Map<String, Long> keptTypes = new TreeMap<>();
        final Map<String, Long> skippedTypes = new TreeMap<>();
        final Map<String, Long> droppedOperators = new TreeMap<>();
        final Map<String, Long> attributes = new TreeMap<>();
        String lastError;
        // Bytes as the JMS library hands them over, the XML after any gzip, and what the network carried.
        long deliveredBytes, payloadBytes, networkMark = networkBytes();
        final Map<String, Long> bodyKinds = new TreeMap<>();

        synchronized void delivered(String kind, boolean gzipped, long bytes) {
            deliveredBytes += bytes;
            bodyKinds.merge(kind + (gzipped ? " gzip" : ""), 1L, Long::sum);
        }

        synchronized void payload(long bytes) {
            payloadBytes += bytes;
        }

        /** Bytes received by this container, which only the collector's connection uses. */
        static long networkBytes() {
            try {
                return Long.parseLong(Files.readString(Path.of("/sys/class/net/eth0/statistics/rx_bytes")).trim());
            } catch (Exception e) {
                return -1;
            }
        }

        static String mb(long bytes) {
            return String.format("%.1f MB", bytes / 1_000_000.0);
        }

        synchronized void message(String root) {
            messages++;
            roots.merge(String.valueOf(root), 1L, Long::sum);
        }

        synchronized void flight(Element flight) {
            flights++;
            NamedNodeMap attrs = flight.getAttributes();
            for (int i = 0; i < attrs.getLength(); i++) {
                attributes.merge(attrs.item(i).getNodeName(), 1L, Long::sum);
            }
        }

        synchronized void kept(String type) {
            kept++;
            keptTypes.merge(type.isEmpty() ? "?" : type, 1L, Long::sum);
        }

        synchronized void skipped(String type) {
            skippedTypes.merge(type, 1L, Long::sum);
        }

        synchronized void dropped(String operator) {
            // Only scheduled airline style codes are counted by name; the rest are lumped together.
            droppedOperators.merge(operator == null ? "other" : operator, 1L, Long::sum);
        }

        synchronized void error(Exception e) {
            errors++;
            lastError = e.getClass().getSimpleName() + ": " + e.getMessage();
        }

        synchronized void report() {
            log("Messages " + messages + ", flight records " + flights + ", kept " + kept + ", errors " + errors);
            log("  Message types " + roots);
            log("  Flight record attributes " + attributes);
            log("  Kept by type " + keptTypes);
            log("  Skipped by type " + skippedTypes);
            log("  Dropped at " + AIRPORT + " " + droppedOperators);
            long network = networkBytes();
            String received = networkMark < 0 || network < 0 ? "unknown" : mb(network - networkMark);
            String ratio = network < 0 || network <= networkMark ? "" :
                    String.format(" (XML is %.1f times the network traffic)", payloadBytes / (double) (network - networkMark));
            log("  Bytes: network " + received + ", delivered " + mb(deliveredBytes) + ", XML " + mb(payloadBytes) + ratio + ", bodies " + bodyKinds);
            if (lastError != null) {
                log("  Last error " + lastError);
            }
            networkMark = network;
            deliveredBytes = payloadBytes = 0;
            bodyKinds.clear();
            messages = flights = kept = errors = 0;
            roots.clear();
            keptTypes.clear();
            skippedTypes.clear();
            droppedOperators.clear();
            attributes.clear();
            lastError = null;
        }
    }
}
