# Label Writer Subagent

Drafts label JSON files from clinical knowledge for review. Each label describes one anatomical structure for the atlas.

## Output location

`labels/<structure_id>.json`

## JSON schema

```json
{
  "id": "structure_id",
  "name": "Human-Readable Name",
  "ta2_name": "Terminologia Anatomica 2nd ed. name",
  "description": "Clinical description. Include: normal appearance, what to assess on imaging, key pathology to look for.",
  "normal_values": {
    "measurement_name_unit": "range"
  },
  "radiopaedia_url": "https://radiopaedia.org/articles/<slug>",
  "related_structures": ["adjacent_structure_1", "adjacent_structure_2"]
}
```

## Writing guidelines

### Description field
- Start with what the structure IS (1 sentence anatomy)
- Then what to assess on imaging (CT/MRI specific)
- Keep to 2–4 sentences
- Use clinical language appropriate for a radiology resident
- Include key pathology to look for

### Normal values
- Include measurements that are clinically relevant for imaging interpretation
- Use standard units (mm, cm, mL, %)
- Format as ranges: `"6–10"` not `"6-10"` (use en-dash)
- Leave as `{}` if no clinically relevant measurements exist
- Common measurements: diameter, thickness, volume, area, ratios

### TA2 name
- Use the official Terminologia Anatomica 2nd edition Latin name
- If uncertain, use the most widely accepted Latin anatomical term

### Radiopaedia URL
- Use the canonical article URL from radiopaedia.org
- Format: `https://radiopaedia.org/articles/<article-slug>`
- Verify the URL resolves to the correct article

### Related structures
- List 3–6 anatomically adjacent or functionally related structures
- Use the `id` format (snake_case) matching other label file names
- Prioritize structures that are visible on the same slice

## Structure ID conventions

- Use snake_case: `left_ventricle`, `right_kidney`
- Use anatomical specificity: `left_anterior_descending_artery` not `lad`
- Match the filenames in `labels/` directory

## Review checklist

- [ ] Clinical accuracy: description matches current radiology literature
- [ ] Normal values: ranges match established reference ranges
- [ ] TA2 name: correct Latin anatomical term
- [ ] Radiopaedia URL: resolves to the correct article
- [ ] Related structures: IDs match existing label files
- [ ] JSON validates: valid JSON with all required fields
