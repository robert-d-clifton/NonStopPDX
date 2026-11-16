FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -q -B dependency:go-offline
COPY src src
RUN mvn -q -B package && mvn -q -B dependency:copy-dependencies -DincludeScope=runtime -DoutputDirectory=target/lib

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/collector.jar /app/collector.jar
COPY --from=build /src/target/lib /app/lib
USER 1000
CMD ["java", "-cp", "/app/collector.jar:/app/lib/*", "pdx.Collector"]
