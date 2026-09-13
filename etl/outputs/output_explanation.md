allowed_human_languages.json
- extract languages from tool records
- delete the non-human languages

candidate_tool_records.json
- extract from aitooldirectory api


enriched_candidate_tool_records_original.json
- test for five tools

enriched_candidate_tool_records_cleaned.json/enriched_candidate_tool_records.json
- manually cleaned only changed 8 field values
- Remove items incorrectly labeled as natural languages (e.g., TypeScript, PHP, Python, JavaScript), since these are programming technologies rather than human languages.
- Normalize language names, such as converting Mandarin / Simplified Chinese / Traditional Chinese into Chinese, and correcting Romania to Romanian.
- Update AI Aware’s price_type field from ["free trial"] to ["free trial", "paid"].

enriched_candidate_tool_records_cleaned.json
- as the input of loading tools