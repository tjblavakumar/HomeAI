# HomeAI — Initial Plan

## The Problem
Every household accumulates a growing pile of electronics, appliances, furniture, and tools —
each with its own user manual, troubleshooting guide, software driver, or accessory list.
Over time, people forget the exact model number, where they bought it, or how to fix a
recurring issue. The information exists somewhere on the internet, but finding it again
means digging through email receipts, guessing search terms, or hunting manufacturer
websites from scratch, every single time.

## The Idea
Build a personal, household-owned knowledge base application:

- A simple web UI, open to anyone in the household, showing category scorecards
  (Electronics, Appliances, Furniture, Tools, etc.) with item counts at a glance.
- Clicking a category reveals the list of items the household owns in it.
- A chat box at the bottom lets anyone type a natural request, e.g.
  *"find the user manual for the Ninja CAFE Luxe3 I bought from Costco"* or
  *"what ink does my Canon GX1020 use?"*.
- Behind the scenes, the app searches the web for the specific brand/model, and comes back
  with a categorized list: user manual, troubleshooting guide, compatible accessories
  (e.g. batteries, ink cartridges), and software/driver links.
- Results are shown as a checklist — the user picks exactly what they want saved.
- Manuals, troubleshooting guides, and accessory info get stored and indexed so the
  chatbot can answer troubleshooting questions directly, without a trip to Google.
  Software drivers/installers are only linked to (never downloaded/hosted or indexed),
  since they go stale and vary by OS/version.

## Expected Outcome
A self-hosted household assistant that:
1. Gives every household member a single place to see what they own, organized by category.
2. Lets anyone add an item via a form, a chat message, or a photo/barcode scan.
3. Automatically finds the right manuals, guides, and accessory info for a given
   brand/model via web search, letting the user choose what to keep.
4. Answers troubleshooting questions conversationally, grounded in the household's own
   saved manuals (retrieval-augmented, with citations back to the source document).
5. Runs first on a local Linux box for development/testing, then packages into Docker so
   it can be deployed anywhere (home server, NAS, cloud) later.

## Out of Scope (v1)
- User accounts/authentication (trusted home network only for now).
- Multi-household / multi-tenant support.
- Native mobile app.
- Hosting or auto-installing software drivers (link-only).
- Cloud deployment automation (a working Docker image is the v1 deliverable).
