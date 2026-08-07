const e = React.createElement;

function NameForm({ name, onSubmit }) {
  const [value, setValue] = React.useState(name);
  return e(
    'form',
    {
      onSubmit: (ev) => { ev.preventDefault(); onSubmit(value.trim()); },
      style: { display: 'flex', gap: '.5rem', marginBottom: '1.5rem' },
    },
    e('input', {
      type: 'text',
      value,
      autoFocus: true,
      placeholder: 'Employee name',
      onChange: (ev) => setValue(ev.target.value),
      style: { flex: 1, marginBottom: 0 },
    }),
    e('button', { type: 'submit', className: 'stamp-btn primary' }, 'View')
  );
}

function HoursTable({ rows }) {
  if (!rows.length) return e('p', null, 'No hours found.');
  return e(
    'table',
    { className: 'ledger' },
    e(
      'thead',
      null,
      e('tr', null, e('th', null, 'Date'), e('th', null, 'Hours'), e('th', null, 'Source'))
    ),
    e(
      'tbody',
      null,
      rows.map((r, i) =>
        e(
          'tr',
          { key: i },
          e('td', null, r.date),
          e('td', { className: 'num' }, r.hours.toFixed(2)),
          e('td', null, r.source)
        )
      )
    )
  );
}

function UnmappedWarning({ codes }) {
  if (!codes.length) return null;
  return e('div', { className: 'unmapped-stamp' }, `UNMAPPED: ${codes.join(', ')}`);
}

function AlDatesPanel({ name, alDates, onChange }) {
  const [date, setDate] = React.useState('');
  const [note, setNote] = React.useState('');

  function add(ev) {
    ev.preventDefault();
    fetch('/api/al', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, date, note }),
    })
      .then((r) => r.json())
      .then((data) => {
        onChange(data.al_dates);
        setDate('');
        setNote('');
      })
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); });
  }

  function remove(id) {
    fetch(`/api/al/${id}/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
      .then((r) => r.json())
      .then((data) => onChange(data.al_dates))
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); });
  }

  return e(
    'div',
    { style: { marginBottom: '1.5rem' } },
    e('h2', null, 'Upcoming AL'),
    e(
      'form',
      { onSubmit: add, style: { display: 'flex', gap: '.5rem', marginBottom: '.75rem' } },
      e('input', {
        type: 'date',
        value: date,
        required: true,
        onChange: (ev) => setDate(ev.target.value),
        style: { marginBottom: 0, flex: '0 0 auto' },
      }),
      e('input', {
        type: 'text',
        value: note,
        placeholder: 'Note (optional)',
        onChange: (ev) => setNote(ev.target.value),
        style: { marginBottom: 0, flex: 1 },
      }),
      e('button', { type: 'submit', className: 'stamp-btn' }, 'Add')
    ),
    alDates.length
      ? e(
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
                  e('button', { type: 'button', className: 'stamp-btn', onClick: () => remove(a.id) }, 'Remove')
                )
              )
            )
          )
        )
      : e('p', null, 'No AL dates recorded.')
  );
}

function DownloadButton({ name }) {
  if (!name) return null;
  return e(
    'a',
    {
      href: `/report.xlsx?name=${encodeURIComponent(name)}`,
      className: 'stamp-btn primary',
      style: { display: 'inline-block' },
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

  function load(n) {
    setName(n);
    if (!n) {
      setRows([]);
      setUnmapped([]);
      setAlDates([]);
      return;
    }
    fetch(`/api/report?name=${encodeURIComponent(n)}`)
      .then((r) => r.json())
      .then((data) => {
        setRows(data.rows);
        setUnmapped(data.unmapped);
        setAlDates(data.al_dates);
      })
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); });
  }

  React.useEffect(() => {
    if (initialName) load(initialName);
  }, []);

  return e(
    React.Fragment,
    null,
    e(NameForm, { name, onSubmit: load }),
    name && e(AlDatesPanel, { name, alDates, onChange: setAlDates }),
    name && e(UnmappedWarning, { codes: unmapped }),
    name && e(HoursTable, { rows }),
    e(DownloadButton, { name: rows.length ? name : '' })
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(e(App));
