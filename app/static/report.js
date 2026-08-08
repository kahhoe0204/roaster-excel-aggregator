const e = React.createElement;

function toJson(r) {
  if (r.status === 401) {
    location.href = '/login';
    throw new Error('unauthorized');
  }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function NameForm({ name, loading, onSubmit }) {
  const [value, setValue] = React.useState(name);
  return e(
    'form',
    {
      onSubmit: (ev) => { ev.preventDefault(); onSubmit(value.trim()); },
      style: { display: 'flex', flexWrap: 'wrap', gap: '.5rem', marginBottom: '1.5rem' },
    },
    e('input', {
      type: 'text',
      value,
      autoFocus: true,
      placeholder: 'Employee name',
      'aria-label': 'Employee name',
      onChange: (ev) => setValue(ev.target.value),
      style: { flex: 1, marginBottom: 0 },
    }),
    e('button', { type: 'submit', className: 'btn', disabled: loading }, loading ? 'Loading…' : 'View')
  );
}

const _MONTH_ABBR = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
const _MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

function monthTabOf(dateStr) {
  const m = dateStr.match(/-([A-Za-z]{3})$/);
  const idx = m ? _MONTH_ABBR.indexOf(m[1].toLowerCase()) : -1;
  return idx === -1 ? 'Other' : _MONTH_NAMES[idx];
}

function groupByMonthTab(rows) {
  const groups = [];
  const indexByTab = {};
  rows.forEach((r) => {
    const tab = monthTabOf(r.date);
    if (!(tab in indexByTab)) {
      indexByTab[tab] = groups.length;
      groups.push({ tab, rows: [] });
    }
    groups[indexByTab[tab]].rows.push(r);
  });
  return groups;
}

function HoursTable({ rows, name }) {
  if (!rows.length) return e('p', { className: 'ledger-empty' }, 'No hours on record.');

  function saveRemark(date, note) {
    fetch('/api/remarks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, date, note }),
    }).catch((err) => console.error(err));
  }

  function renderGroup(group) {
    return e(
      'div',
      { key: group.tab, style: { marginBottom: '1.5rem' } },
      e('h3', null, group.tab),
      e(
        'div',
        { className: 'table-wrap' },
        e(
          'table',
          { className: 'ledger' },
          e(
            'thead',
            null,
            e(
              'tr', null,
              e('th', null, 'Date'), e('th', null, 'Day'), e('th', null, 'Hours'),
              e('th', null, 'Source'), e('th', null, 'Operation Period'), e('th', null, 'Remark')
            )
          ),
          e(
            'tbody',
            null,
            group.rows.map((r, i) =>
              e(
                'tr',
                { key: i },
                e('td', null, r.date),
                e('td', null, r.day),
                e('td', { className: 'num' }, r.hours.toFixed(2)),
                e('td', null, r.source),
                e('td', null, r.operation_hours || ''),
                e(
                  'td',
                  null,
                  e('input', {
                    type: 'text',
                    defaultValue: r.remark || '',
                    placeholder: 'e.g. bank in',
                    'aria-label': `Remark for ${r.date}`,
                    onBlur: (ev) => saveRemark(r.date, ev.target.value.trim()),
                    style: { width: '100%', marginBottom: 0 },
                  })
                )
              )
            )
          )
        )
      )
    );
  }

  return e(React.Fragment, null, groupByMonthTab(rows).map(renderGroup));
}

function UnmappedWarning({ codes, onResolved }) {
  const [hoursByKey, setHoursByKey] = React.useState({});
  const [savingKey, setSavingKey] = React.useState(null);

  if (!codes.length) return null;

  const keyOf = (u) => `${u.spreadsheet_id}:${u.code}`;

  function submit(u, hours) {
    const key = keyOf(u);
    setSavingKey(key);
    fetch('/api/codes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spreadsheet_id: u.spreadsheet_id, code: u.code, hours }),
    })
      .then(toJson)
      .then(() => onResolved())
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); })
      .finally(() => setSavingKey(null));
  }

  function save(u) {
    const hours = parseFloat(hoursByKey[keyOf(u)]);
    if (!hours || hours <= 0) { alert(`Enter hours for ${u.code}`); return; }
    submit(u, hours);
  }

  function ignore(u) {
    submit(u, null);
  }

  return e(
    'div',
    { className: 'alert alert-warning' },
    e('div', null, `UNMAPPED: ${codes.map((u) => `${u.code} (${u.label})`).join(', ')}`),
    codes.map((u) => {
      const key = keyOf(u);
      return e(
        'div',
        { key, style: { display: 'flex', gap: '.5rem', alignItems: 'center', marginTop: '.5rem' } },
        e('span', null, `${u.code} on ${u.label} is how many hours?`),
        e('input', {
          type: 'number',
          step: '0.5',
          min: '0',
          placeholder: 'hours',
          'aria-label': `Hours for ${u.code} on ${u.label}`,
          value: hoursByKey[key] || '',
          disabled: savingKey === key,
          onChange: (ev) => setHoursByKey({ ...hoursByKey, [key]: ev.target.value }),
          style: { width: '6rem', marginBottom: 0 },
        }),
        e(
          'button',
          { type: 'button', className: 'btn', disabled: savingKey === key, onClick: () => save(u) },
          savingKey === key ? 'Saving…' : 'Save'
        ),
        e(
          'button',
          {
            type: 'button',
            className: 'btn',
            disabled: savingKey === key,
            title: 'Not a working-hour code — leave it out of the report',
            onClick: () => ignore(u),
          },
          'Ignore'
        )
      );
    })
  );
}

function AlDatesPanel({ name, alDates, onChange }) {
  const [date, setDate] = React.useState('');
  const [note, setNote] = React.useState('');
  const [adding, setAdding] = React.useState(false);
  const [removingId, setRemovingId] = React.useState(null);

  function add(ev) {
    ev.preventDefault();
    setAdding(true);
    fetch('/api/al', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, date, note }),
    })
      .then(toJson)
      .then((data) => {
        onChange(data.al_dates);
        setDate('');
        setNote('');
      })
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); })
      .finally(() => setAdding(false));
  }

  function remove(id) {
    setRemovingId(id);
    fetch(`/api/al/${id}/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
      .then(toJson)
      .then((data) => onChange(data.al_dates))
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); })
      .finally(() => setRemovingId(null));
  }

  return e(
    'div',
    { className: 'alert alert-info' },
    e('h2', null, 'Upcoming AL'),
    e(
      'form',
      { onSubmit: add, style: { display: 'flex', flexWrap: 'wrap', gap: '.5rem', marginBottom: '.75rem' } },
      e('input', {
        type: 'date',
        value: date,
        required: true,
        'aria-label': 'AL date',
        onChange: (ev) => setDate(ev.target.value),
        disabled: adding,
        style: { marginBottom: 0, flex: '0 0 auto' },
      }),
      e('input', {
        type: 'text',
        value: note,
        placeholder: 'Note (optional)',
        'aria-label': 'Note',
        onChange: (ev) => setNote(ev.target.value),
        disabled: adding,
        style: { marginBottom: 0, flex: 1 },
      }),
      e('button', { type: 'submit', className: 'btn', disabled: adding }, adding ? 'Adding…' : 'Add')
    ),
    alDates.length
      ? e(
          'div',
          { className: 'table-wrap' },
          e(
            'table',
            { className: 'ledger' },
            e('thead', null, e('tr', null, e('th', null, 'Date'), e('th', null, 'Note'), e('th', null, ''))),
            e(
              'tbody',
              null,
              alDates.map((a) =>
                e(
                  'tr',
                  { key: a.id },
                  e('td', null, a.date),
                  e('td', null, a.note),
                  e(
                    'td',
                    null,
                    e(
                      'button',
                      { type: 'button', className: 'btn', disabled: removingId === a.id, onClick: () => remove(a.id) },
                      removingId === a.id ? 'Removing…' : 'Remove'
                    )
                  )
                )
              )
            )
          )
        )
      : e('p', { className: 'ledger-empty' }, 'No AL dates recorded.')
  );
}

function DownloadButton({ name }) {
  if (!name) return null;
  return e(
    'a',
    {
      href: `/report.xlsx?name=${encodeURIComponent(name)}`,
      className: 'btn btn-primary',
    },
    'Download .xlsx'
  );
}

function App() {
  const root = document.getElementById('root');
  const initialName = root.dataset.initialName || '';
  const [name, setName] = React.useState(initialName);
  const [rows, setRows] = React.useState([]);
  const [unmapped, setUnmapped] = React.useState([]);
  const [alDates, setAlDates] = React.useState([]);
  const [loading, setLoading] = React.useState(false);

  function load(n) {
    setName(n);
    if (!n) {
      setRows([]);
      setUnmapped([]);
      setAlDates([]);
      return;
    }
    setLoading(true);
    fetch(`/api/report?name=${encodeURIComponent(n)}`)
      .then(toJson)
      .then((data) => {
        setRows(data.rows);
        setUnmapped(data.unmapped);
        setAlDates(data.al_dates);
      })
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); })
      .finally(() => setLoading(false));
  }

  React.useEffect(() => {
    if (initialName) load(initialName);
  }, []);

  return e(
    React.Fragment,
    null,
    e(NameForm, { name, loading, onSubmit: load }),
    loading && e('p', { className: 'ledger-empty' }, 'Fetching hours from the sheet…'),
    !loading && name && e(AlDatesPanel, { name, alDates, onChange: setAlDates }),
    !loading && name && e(UnmappedWarning, { codes: unmapped, onResolved: () => load(name) }),
    !loading && name && e(HoursTable, { rows, name }),
    !loading && e(DownloadButton, { name: rows.length ? name : '' })
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(e(App));
