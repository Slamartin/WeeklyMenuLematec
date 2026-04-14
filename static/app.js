const DAY_LABELS = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
};

const DAY_ORDER = Object.keys(DAY_LABELS);

const state = {
  selectedDay: getTodayKey(),
  todayOnly: false,
  payload: null,
};

const loadingState = document.getElementById("loading-state");
const errorState = document.getElementById("error-state");
const menuContent = document.getElementById("menu-content");
const errorMessage = document.getElementById("error-message");
const weekLabel = document.getElementById("week-label");
const statusText = document.getElementById("status-text");
const dayTabs = document.getElementById("day-tabs");
const warningBox = document.getElementById("warning-box");

document.getElementById("today-button").addEventListener("click", () => {
  state.todayOnly = !state.todayOnly;
  state.selectedDay = getTodayKey();
  render();
});

document.getElementById("reload-button").addEventListener("click", () => {
  loadMenu({ bustCache: true });
});

loadMenu();

async function loadMenu() {
  showLoading();

  try {
    const response = await fetch("/menu", { headers: { Accept: "application/json" } });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }

    state.payload = await response.json();
    state.selectedDay = DAY_ORDER.includes(state.selectedDay) ? state.selectedDay : getTodayKey();
    render();
  } catch (error) {
    loadingState.classList.add("hidden");
    errorState.classList.remove("hidden");
    menuContent.classList.add("hidden");
    errorMessage.textContent = error.message || "We could not load the menus right now.";
    weekLabel.textContent = "Unavailable";
    statusText.textContent = "Load failed";
  }
}

function render() {
  loadingState.classList.add("hidden");
  errorState.classList.add("hidden");
  menuContent.classList.remove("hidden");

  const meta = state.payload?._meta ?? {};
  const errors = meta.errors ?? {};
  const hasErrors = Object.keys(errors).length > 0;

  weekLabel.textContent = meta.weekLabel || "Current week";
  statusText.textContent = hasErrors ? "Loaded with partial warnings" : "Up to date";

  renderTabs();
  renderRestaurant("bistro22-content", state.payload?.bistro22 ?? {});
  renderRestaurant("cookpoint-content", state.payload?.cookpoint ?? {});

  if (hasErrors) {
    warningBox.classList.remove("hidden");
    warningBox.innerHTML = Object.entries(errors)
      .map(([source, message]) => `<p><strong>${source}</strong>: ${escapeHtml(message)}</p>`)
      .join("");
  } else {
    warningBox.classList.add("hidden");
    warningBox.innerHTML = "";
  }
}

function renderTabs() {
  dayTabs.innerHTML = "";

  DAY_ORDER.forEach((day) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "day-tab";
    button.textContent = DAY_LABELS[day];

    if (day === state.selectedDay && !state.todayOnly) {
      button.classList.add("active");
    }
    if (day === getTodayKey()) {
      button.classList.add("today");
    }

    button.addEventListener("click", () => {
      state.todayOnly = false;
      state.selectedDay = day;
      render();
    });

    dayTabs.appendChild(button);
  });
}

function renderRestaurant(containerId, restaurantData) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  const visibleDays = state.todayOnly ? [getTodayKey()] : DAY_ORDER;

  visibleDays.forEach((day) => {
    const panel = document.createElement("section");
    panel.className = "day-panel";
    if (day === getTodayKey()) {
      panel.classList.add("today");
    }
    if (!state.todayOnly && day !== state.selectedDay) {
      panel.classList.add("hidden");
    }

    const title = document.createElement("h3");
    title.className = "day-name";
    title.textContent = DAY_LABELS[day];
    panel.appendChild(title);

    const meals = Array.isArray(restaurantData[day]) ? restaurantData[day] : [];
    if (meals.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty-copy";
      empty.textContent = "No meals were parsed for this day.";
      panel.appendChild(empty);
    } else {
      const list = document.createElement("ul");
      list.className = "menu-list";
      meals.forEach((meal) => {
        const item = document.createElement("li");
        item.textContent = meal;
        list.appendChild(item);
      });
      panel.appendChild(list);
    }

    container.appendChild(panel);
  });
}

function showLoading() {
  loadingState.classList.remove("hidden");
  errorState.classList.add("hidden");
  menuContent.classList.add("hidden");
  weekLabel.textContent = "Loading...";
  statusText.textContent = "Fetching menus";
}

function getTodayKey() {
  const day = new Intl.DateTimeFormat("en-US", { weekday: "long" })
    .format(new Date())
    .toLowerCase();
  return DAY_ORDER.includes(day) ? day : "monday";
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
