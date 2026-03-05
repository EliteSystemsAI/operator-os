---
name: drive
description: >
  Save, find, upload, or organise files in Zac's Google Drive.
  Use when asked to: "save to Drive", "upload to Drive", "find in Drive",
  "put this in Drive", "what's in Drive", "move to Drive", "check Drive".
  Uses the google-drive MCP tools. Always follows naming conventions and
  folder map in drive/folder-map.md.
---

# Google Drive Skill

## Goal
Correctly route any file, output, or content to the right Drive folder using
the folder map and naming conventions. Never guess folder structure — always
reference folder-map.md.

---

## Step 1 — Identify the content type

Determine what is being saved or found:

| Type | Drive section |
|---|---|
| Comparison carousel (PNG slides) | Content → Comparison Carousels |
| Instagram carousel (non-comparison) | Content → Carousels |
| Reel video file | Content → Reel Videos |
| Thumbnail image | Content → Thumbnails |
| Reel script (markdown/text) | Scripts → Reel Scripts |
| Carousel script | Scripts → Carousel Scripts |
| Ad script / copy | Scripts → Ad Scripts |
| Meta ad creative (image/video) | Ads → Meta Ads — Creatives |
| Ad performance report | Ads → Meta Ads — Reports |
| Logo, font, colour file | Brand Assets |
| Reference doc / research | Knowledge Base |
| Anything old / superseded | Archive |

---

## Step 2 — Apply naming conventions

**Comparison carousels:**
- Batch folder: `YYYY-MM-DD — {Topic} Carousel ({n} slides)`
- Slide files: `Slide 01 — {Descriptive Name}.png`

**Other content:**
- `YYYY-MM-DD — {Topic} {Type}.{ext}`
- Examples: `2026-02-28 — AI Lead Followup Script.md`
- Examples: `2026-02-28 — New Leads Ad — V2.png`

**Brand assets:**
- Just the asset name + version if relevant: `EliteSystems-Logo-Primary.png`

Always use today's date in YYYY-MM-DD format unless the content has a specific date.

---

## Step 3 — Execute the Drive operation

Use the google-drive MCP tools. Get folder IDs from folder-map.md.

**To upload a file:**
```
create_file(name="Slide 01 — Lead Followup.png", parent_folder_id="...", content=<file>)
```

**To create a batch folder then upload multiple files:**
1. `create_file` with `mimeType: application/vnd.google-apps.folder` and the correct parent ID
2. Upload each file into the new folder ID

**To find a file:**
```
search_files(query="lead followup comparison")
```

**To list a folder's contents:**
```
get_file(file_id="<folder_id>")
```
or search with `parent_folder_id` filter.

**To move a file:**
```
move_file(file_id="...", new_parent_id="...")
```

---

## Step 4 — Confirm and report back

After every Drive operation, report:
- What was saved/found/moved
- The Drive folder it landed in (human-readable path, not just ID)
- A direct Drive link if available

---

## Rules

- **Never create a new top-level folder** without asking first. Always use the existing structure.
- **Always use dated batch subfolders** for sets of generated content (carousels, ad batches).
- **Never overwrite** without confirming if a file with the same name already exists.
- If content type is unclear, ask before uploading — wrong folder is worse than a pause.
- Reference files from folder-map.md for all folder IDs. Do not hardcode IDs in conversation.
