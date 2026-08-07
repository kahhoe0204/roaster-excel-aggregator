const e = React.createElement;

function toJson(r) {
  if (r.status === 401) {
    location.href = '/login';
    throw new Error('unauthorized');
  }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function NameForm({ name, onSubmit }) {
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
    e('button', { type: 'submit', className: 'btn' }, 'View')
  );
}

function HoursTable({ rows }) {
  if (!rows.length) return e('p', { className: 'ledger-empty' }, 'No hours on record.');
  return e(
    'div',
    { className: 'table-wrap' },
    e(
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
    )
  );
}

function UnmappedWarning({ codes }) {
  if (!codes.length) return null;
  return e('div', { className: 'alert alert-warning' }, `UNMAPPED: ${codes.join(', ')}`);
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
      .then(toJson)
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
      .then(toJson)
      .then((data) => onChange(data.al_dates))
      .catch((err) => { console.error(err); alert('Something went wrong — please try again.'); });
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
        style: { marginBottom: 0, flex: '0 0 auto' },
      }),
      e('input', {
        type: 'text',
        value: note,
        placeholder: 'Note (optional)',
        'aria-label': 'Note',
        onChange: (ev) => setNote(ev.target.value),
        style: { marginBottom: 0, flex: 1 },
      }),
      e('button', { type: 'submit', className: 'btn' }, 'Add')
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
                    e('button', { type: 'button', className: 'btn', onClick: () => remove(a.id) }, 'Remove')
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

  function load(n) {
    setName(n);
    if (!n) {
      setRows([]);
      setUnmapped([]);
      setAlDates([]);
      return;
    }
    fetch(`/api/report?name=${encodeURIComponent(n)}`)
      .then(toJson)
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
