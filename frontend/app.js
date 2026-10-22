// The API is served from the same domain under /api (CloudFront in AWS,
// nginx locally), so relative URLs work everywhere and no CORS is needed.
const API = "/api";

const list = document.getElementById("events");
const statusEl = document.getElementById("status");
const dialog = document.getElementById("register-dialog");
const form = document.getElementById("register-form");
const message = document.getElementById("form-message");
let currentEventId = null;

async function loadEvents() {
  try {
    const resp = await fetch(`${API}/events`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const events = await resp.json();
    statusEl.textContent = events.length ? "" : "No upcoming events yet.";
    list.replaceChildren(...events.map(renderEvent));
  } catch (err) {
    statusEl.textContent = "Could not load events. Please try again in a moment.";
    console.error(err);
  }
}

function renderEvent(event) {
  const li = document.createElement("li");
  li.className = "event";
  const when = new Date(event.starts_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  const full = event.seats_left <= 0;

  const h3 = document.createElement("h3");
  h3.textContent = event.name;
  const meta = document.createElement("p");
  meta.textContent = `${when} · ${event.venue}`;
  const seats = document.createElement("p");
  seats.className = full ? "seats full" : "seats";
  seats.textContent = full ? "Full" : `${event.seats_left} of ${event.capacity} seats left`;
  const button = document.createElement("button");
  button.textContent = full ? "Full" : "Register";
  button.disabled = full;
  button.addEventListener("click", () => openForm(event));

  li.append(h3, meta, seats, button);
  return li;
}

function openForm(event) {
  currentEventId = event.event_id;
  document.getElementById("register-title").textContent = `Register: ${event.name}`;
  message.textContent = "";
  form.reset();
  dialog.showModal();
}

document.getElementById("cancel").addEventListener("click", () => dialog.close());

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const submit = document.getElementById("submit");
  submit.disabled = true; // stops double-click double submissions
  message.textContent = "Registering…";
  try {
    const resp = await fetch(`${API}/events/${currentEventId}/registrations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    const body = await resp.json();
    if (resp.ok) {
      message.textContent = `Confirmed! Registration ID: ${body.registration_id}`;
      loadEvents();
    } else {
      // Show the request id so a student can quote it when asking for help.
      const detail = typeof body.detail === "string" ? body.detail : "Please check your details.";
      message.textContent = `${detail} (ref: ${resp.headers.get("X-Request-Id") ?? "n/a"})`;
    }
  } catch (err) {
    message.textContent = "Network error. Your registration was not sent; please try again.";
  } finally {
    submit.disabled = false;
  }
});

fetch(`${API}/health`)
  .then((r) => r.json())
  .then((h) => (document.getElementById("version").textContent = `build ${h.version}`))
  .catch(() => {});

loadEvents();
