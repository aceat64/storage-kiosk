# storage-kiosk

[![asciicast](https://asciinema.org/a/480893.svg)](https://asciinema.org/a/480893)

## User Interaction Flow

- Scan badge
  - If not valid, fail and exit
  - If banned, fail and exit
- Check if member has an existing ticket
  - If ticket exists, finish out ticket, exit
- Find all open spots
- Prompt user to select a spot
- Create ticket for spot
