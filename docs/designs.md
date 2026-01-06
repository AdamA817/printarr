# Designs

The Designs page is your catalog of 3D-printable models discovered from monitored channels.

## Browsing Designs

### Views

Toggle between views using the buttons in the header:

| View | Best For |
|------|----------|
| **Grid** | Visual browsing with thumbnails |
| **List** | Detailed info, sorting, bulk actions |

### Filtering

Use filters to narrow down designs:

| Filter | Options |
|--------|---------|
| **Status** | All, Wanted, Downloading, Downloaded, Available |
| **Channel** | Filter by source channel |
| **File Type** | STL, 3MF, OBJ, Archives |
| **Has Preview** | Only show designs with thumbnails |

### Sorting

Sort by:
- **Date** (newest/oldest)
- **Title** (A-Z/Z-A)
- **Channel**
- **Size**

### Searching

Use the search box to find designs by:
- Title
- Designer name
- Description text
- File names

## Design Details

Click a design to see its detail page:

### Overview Tab

- **Title**: Design name (editable)
- **Designer**: Creator name from channel or Thangs
- **Source**: Link to original Telegram post
- **Files**: List of detected files
- **Preview**: Rendered STL thumbnail (if available)

### Files Tab

Shows all files associated with the design:
- File name and type
- Size
- Download status
- Individual file actions

### Activity Tab

History of actions on this design:
- When discovered
- Download attempts
- Render jobs
- Status changes

## Design Statuses

| Status | Meaning |
|--------|---------|
| **Available** | Detected but not marked for download |
| **Wanted** | Marked for download, waiting in queue |
| **Downloading** | Currently being downloaded |
| **Downloaded** | Files successfully downloaded |
| **Failed** | Download failed (check activity for details) |

## Actions

### Single Design

From the detail page or grid card:

| Action | Description |
|--------|-------------|
| **Want** | Add to download queue |
| **Download Now** | Priority download immediately |
| **Preview** | Open lightbox with images/renders |
| **Edit** | Modify title, designer, tags |
| **Delete** | Remove from catalog |

### Bulk Actions

In list view, select multiple designs:

1. Click checkboxes to select
2. Use bulk action bar at top
3. Available actions:
   - Mark as Wanted
   - Mark as Downloaded
   - Delete selected

## Thangs Integration

Printarr can link designs to [Thangs](https://thangs.com) for enhanced metadata.

### Automatic Linking

If FlareSolverr is configured, Printarr automatically:
1. Searches Thangs for matching designs
2. Links high-confidence matches
3. Imports metadata (description, tags, images)

### Manual Linking

1. Open design detail
2. Click **Link to Thangs**
3. Search for the design
4. Select the correct match

### Linked Data

From Thangs, Printarr imports:
- Description
- Tags
- Designer information
- Additional preview images
- Remix/original relationships

## Preview Generation

Printarr generates STL previews using stl-thumb.

### Automatic Rendering

When enabled (`PRINTARR_AUTO_QUEUE_RENDER_AFTER_IMPORT=true`):
1. Import completes
2. Render job queued automatically
3. Preview appears when done

### Manual Rendering

1. Open design detail
2. Click **Render Preview**
3. Wait for job to complete

### Preview Quality

Renders are created at multiple angles:
- Front view (default thumbnail)
- Isometric view
- Top view

## Merging Designs

Sometimes designers split files across multiple messages. Printarr can merge them:

### Automatic Detection

Printarr suggests merges when:
- Same channel, close timestamps
- Similar file naming patterns
- Sequential part numbers

### Manual Merge

1. Open the primary design
2. Click **Merge**
3. Search for related designs
4. Select designs to merge
5. Files combine into one design

## Tags

Organize designs with custom tags.

### Adding Tags

1. Open design detail
2. Click **Edit**
3. Add tags (comma-separated)
4. Save

### Filtering by Tag

Use the tag filter in the designs list to show only designs with specific tags.

## Troubleshooting

### Design Not Appearing

- Check the source channel is enabled
- Verify the post contains 3D files
- Look in Activity for processing errors

### Wrong Designer Name

- Edit the design manually
- Or link to Thangs for accurate metadata

### Preview Not Generating

- Check render job in Activity
- Verify stl-thumb is working (check logs)
- Some files may be incompatible
