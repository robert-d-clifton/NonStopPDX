# Destination stories

One file per destination, named by its airport code, like `AZA.md`. The fields at the top are:

| Field | What goes in it |
|-------|-----------------|
| `iata` | Airport code. Matches the file name. |
| `city` | City name, to make the file easy to find. |
| `status` | `placeholder` until a story is written, then `draft` or `ready`. |
| `headline` | The story's title. |
| `photo` | Path or link to a photo, once there is one. |
| `photo_credit` | Who took the photo, and its license if it isn't ours. |
| `credits` | Anyone else to credit, like a source we drew from. |

The story itself goes below the fields, as plain Markdown.

`python3 -m sync.seed_stories` adds a placeholder for any new destination. It never changes a file that already exists, and it lists stories whose route has left the route list.
