# Problem 8 - Agent dashboard design

## Visual direction

- **Yale and Bulldog identity:** a compact Yale-style shield with a custom `Y`, a small Bulldog paw mark, and New Haven service-desk language. The brand treatment is text and hand-authored vector shapes; it does not depend on outside logos or photo assets.
- **Palette:** deep Yale navy (`#0f2e5f`) for the header and primary run button, midnight blue (`#092149`) for the top bar, cool silver and slate for dividers and secondary labels, and white panels over a pale blue-gray canvas. Green marks resolved work and the live connection; amber marks open work and the approval checkpoint.
- **Layout:** a compact cash balance card sits beside the page title. A horizontal team roster keeps the lead and specialists visible. The main workspace pairs the three-ticket board with the selected case file and a scrollable live conversation feed. Cards and panels collapse into a single column on narrow screens.
- **Interaction:** ticket cards select the active case; the run button starts the team and the activity feed appends each progress update. A payment or purchase recommendation opens an explicit approval modal with a required confirmation checkbox. The modal explains that approval debits checking and that purchases are recorded locally without contacting a vendor.

## Agent identities and icons

Kakashi Hatake is the Boss and team lead. Each specialist is represented as one of his students, with a distinct emoji mark and color treatment:

| Backend role | Character | Dashboard icon | Color cue |
|---|---|---|---|
| Boss | Kakashi Hatake | Masked ninja - silver and slate | Silver and slate |
| Inventory | Naruto Uzumaki | Spiral | Warm orange |
| Accounting | Sakura Haruno | Cherry blossom | Soft pink |
| Facilities | Sasuke Uchiha | Lightning | Indigo |
| Customer Service | Sai | Brush | Blue-green |

The dashboard uses 🥷, 🌀, 🌸, ⚡, and 🖌️ marks in the roster, activity feed, and final agent summaries so readers can follow who is speaking and what role they are handling.
