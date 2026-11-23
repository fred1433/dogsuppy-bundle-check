/**
 * Exceptions tab: one row per row of the BigQuery view checks_all, refreshed each morning.
 * Rows that were not there on the previous run are coloured; rows that disappeared are listed
 * under "Cleared since last run". Provided to install; it was not executed for the demo: it needs
 * your project, the BigQuery advanced service enabled in the Apps Script editor, and your own
 * authorisation.
 *
 * The REST API returns a TIMESTAMP as float seconds ("1.763913282E9") and a NUMERIC without its
 * trailing zeros ("-16"), and Sheets turns a SKU such as 05430003031827 into a number. So the query
 * formats both in SQL, and the key column is set to plain text before the values are written.
 *
 * Set PROJECT_ID and VIEW, run refreshExceptions() once by hand, then installDailyTrigger().
 */
const PROJECT_ID = 'your-gcp-project';
const VIEW = '`your-gcp-project.reporting.checks_all`';
const SHEET = 'Exceptions';
const COLUMNS = ['check_name', 'severity', 'store', 'key', 'expected', 'actual', 'delta', 'evidence_url', 'read_at'];
const NEW_ROW = '#fde3df';      // pale coral: appeared since the last run
const NOT_CHECKED = '#eef1f0';  // grey: the rule could not run on this row
const TZ = 'Europe/Brussels';
const QUERY = [
  'SELECT check_name, severity, store, key,',
  "  IF(expected IS NULL, NULL, FORMAT('%.2f', expected)) AS expected,",
  "  IF(actual IS NULL, NULL, FORMAT('%.2f', actual)) AS actual,",
  "  IF(delta IS NULL, NULL, FORMAT('%.2f', delta)) AS delta,",
  '  evidence_url,',
  "  FORMAT_TIMESTAMP('%F %R', read_at, '" + TZ + "') AS read_at",
  'FROM ' + VIEW,
  'ORDER BY check_name, store, key',
].join('\n');

function refreshExceptions() {
  const rows = queryView_();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET) || ss.insertSheet(SHEET);
  const props = PropertiesService.getDocumentProperties();
  const before = new Set(JSON.parse(props.getProperty('lastKeys') || '[]'));
  const keyOf = r => [r[0], r[2], r[3]].join('|');           // check_name | store | key
  const now = new Set(rows.map(keyOf));

  sheet.clear();
  sheet.getRange(1, 1, 1, COLUMNS.length).setValues([COLUMNS]).setFontWeight('bold');
  sheet.getRange(1, COLUMNS.length + 2).setValue('Last run: ' + Utilities.formatDate(new Date(), TZ, 'yyyy-MM-dd HH:mm') + ' (' + TZ + ')');
  if (rows.length) {
    sheet.getRange(2, COLUMNS.indexOf('key') + 1, rows.length, 1).setNumberFormat('@');          // keeps 05430003031827 as text
    sheet.getRange(2, COLUMNS.indexOf('expected') + 1, rows.length, 3).setNumberFormat('0.00');  // expected, actual, delta
    sheet.getRange(2, 1, rows.length, COLUMNS.length).setValues(rows);
    rows.forEach((r, i) => {
      const colour = r[1] === 'not_checked' ? NOT_CHECKED : (before.has(keyOf(r)) ? null : NEW_ROW);
      if (colour) sheet.getRange(i + 2, 1, 1, COLUMNS.length).setBackground(colour);
    });
  } else {
    sheet.getRange(2, 1).setValue('0 rows: every check passed on this run.');
  }
  const cleared = [...before].filter(k => !now.has(k));
  if (cleared.length) {
    const start = Math.max(rows.length, 1) + 3;
    sheet.getRange(start, 1).setValue('Cleared since last run').setFontWeight('bold');
    sheet.getRange(start + 1, 1, cleared.length, 1).setValues(cleared.map(k => [k]));
  }
  props.setProperty('lastKeys', JSON.stringify([...now]));
}

function queryView_() {
  const request = { query: QUERY, useLegacySql: false };
  let res = BigQuery.Jobs.query(request, PROJECT_ID);
  const jobId = res.jobReference.jobId;
  while (!res.jobComplete) {
    Utilities.sleep(1000);
    res = BigQuery.Jobs.getQueryResults(PROJECT_ID, jobId);
  }
  let rows = res.rows || [];
  while (res.pageToken) {
    res = BigQuery.Jobs.getQueryResults(PROJECT_ID, jobId, { pageToken: res.pageToken });
    rows = rows.concat(res.rows || []);
  }
  return rows.map(r => r.f.map(c => c.v === null ? '' : c.v));
}

function installDailyTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'refreshExceptions')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('refreshExceptions').timeBased().everyDays(1).atHour(7).create();
}
