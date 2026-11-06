# PROTOTYPE — throwaway (branch `prototype/ag-ui-screen`, never merge)

Answers the Wayfinder ticket "What does the human see during an Investigation? (AG-UI screen prototype)".

Open `investigation-screen.html` in a browser (double-click). No backend: a mock AG-UI event stream plays in the page.

- Black bar: switch layout A Cockpit / B Feed / C Report-first (or ← →), play/pause, speed, jump to each interrupt (Question, RCA gate, Fix gate, Recovery), simulate a backend outage, show the raw event log.
- Model output and quoted log lines render as plain text; links only to allowlisted hosts; no images load (see Finding F5 and the follow-up answer).
