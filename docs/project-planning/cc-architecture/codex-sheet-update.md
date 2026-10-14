# Codex task: update the CC and Architecture rows in the live AI4Research sheet

**For:** Codex, using its spreadsheet or browser skills on the live shared AI4Research project sheet. **Prepared:** October 14, 2026.

## Goal

Make the Capability Capsules rows (WBS 1.x) and the Architecture rows (WBS 8.x) in the live sheet match the target rows in [cc-arch-target-rows.json](cc-arch-target-rows.json). Change nothing else. Other people edit the sheet while you work, so find rows by WBS, never by a remembered row number.

## Inputs

| File | Use |
|---|---|
| [cc-arch-target-rows.json](cc-arch-target-rows.json) | The exact target rows, in display order, for both blocks. This is the data to write |
| [workbook-handoff.md](workbook-handoff.md) | Why each row exists, the conditional rows and the checks. Read sections 1, 7 and 8 |
| Live sheet | Tabs "Main Table" and "Timeline" |

Each JSON row has: `component`, `wbs`, `name`, `owner`, `status`, `start`, `end`, `expected_result`, `work_details`, `metric`, `resources`, `depends_on`, `item_type`, `schedule`, `risk_response` and `level`.
- Dates are ISO strings. `ROLLUP` means the cell is a formula over its child rows, not a typed date.
- `level` is the row's outline level: 0 for the component, 1 for a task, 2 for a subtask or milestone.

## How the sheet is built

- **Main Table columns A to P** are: Component, WBS, Name, Owner, Status, Start, End / due, Expected result, Work details, Metric, Resources, Depends on, Item type, Duration (days), Schedule, Risk / response.
- **Subtask dates** are written as formulas, for example `=DATE(2026,10,19)`.
- **Component and task rows** roll up dates from their children. Use `=MIN(F<first>:F<last>)` for start and `=MAX(G<first>:G<last>)` for end, over the child rows.
- **Duration** in column N is `=IF(AND(ISNUMBER(F<r>),ISNUMBER(G<r>)),NETWORKDAYS(F<r>,G<r>),"")`.
- **Timeline** row r shows Main Table row r minus 4. Every Timeline cell is a relative formula, for example Timeline A9 is `=IF('Main Table'!A5="","",'Main Table'!A5)`. Its bar cells (H onward) are also relative formulas.
  - Inserting Main Table rows does not create Timeline rows. The new Main Table rows need matching Timeline rows.
- **Rows are grouped by outline level** in both tabs. These groups drive the 1, 2 and 3 zoom buttons.

## Steps

Re-read the sheet before every step. If a row you need has moved, find it again by WBS.

1. **Read.** Find the first and last row of each block: rows whose column A is "Capability Capsules", and rows whose column A is "Architecture". Each block must be contiguous. If it is not, stop and report.
2. **Compare.** List, by WBS, the rows to add, the rows to delete, the rows to change and the rows already correct. Rows in the live block that are not in the JSON are someone else's additions. Keep them at the end of their block and report them. Never delete them. Show the list to the user before writing.
3. **Make room.** Inside each block, insert blank rows below the component row until the block has as many rows as the JSON block plus any kept extra rows. Insert the same number of rows at the matching place in the Timeline (Main Table row plus 4).
4. **Write the Main Table.** Write each JSON row in order, starting at the block's component row.
   - Write every column except Duration and the rollup dates, which get the formulas above.
   - Keep the live `status` for rows that already existed. The JSON already carries it.
   - Copy the cell format of an existing row of the same item type.
   - Set the outline level from `level`.
5. **Write the Timeline.** For every Timeline row of the two blocks, copy the formulas of one existing Timeline subtask row, so each row points at its own Main Table row. Copy the format of an existing Timeline row of the same item type, and set the same outline level as its Main Table row.
6. **Work in small writes.** Write one block at a time, in batches of no more than about 20 rows. Re-check the block boundaries between batches. If someone inserts rows inside a block while you work, stop, re-read and continue from the first row that does not match.

## Do not

- Change any row outside the two blocks. The only dependency edits outside them (RSI 3.1.3 and 3.2.1) are already done.
- Replace, re-upload or re-sort the whole sheet.
- Type over formula cells in other components, or change conditional formatting or validation rules.
- Put dates or people's names into text columns.

## Check when finished

1. Each block's WBS sequence in the Main Table matches the JSON order exactly, apart from reported extra rows.
2. Every Timeline row from the first CC row to the last Architecture row shows the same WBS and name as its Main Table row (Main Table row plus 4).
3. The rows `1.0`, `1.1`, `8.0` and the other task rows show real dates, not serial numbers such as 46308.
4. No subtask lasts more than three working days. Milestones are zero days.
5. Every ID in Depends on exists in the sheet, except the 2027 PRD placeholders written as "PRD for ... (row to be added by PRD owner)".
6. Other components' rows have the same values and formulas as before.

## Report

Rows added, deleted and changed, by WBS. Extra rows kept. Any check that failed and why. Any conflict with someone else's edit, listed and not resolved.
