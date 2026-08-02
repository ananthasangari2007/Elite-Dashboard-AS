const root = document.documentElement;
const savedTheme = localStorage.getItem("elite-theme") || "light";

function applyTheme(theme) {
    root.dataset.theme = theme;
    localStorage.setItem("elite-theme", theme);
    document.querySelectorAll("[data-theme-icon]").forEach((icon) => {
        icon.textContent = theme === "dark" ? "☼" : "☾";
    });
}

applyTheme(savedTheme);

document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
        applyTheme(root.dataset.theme === "dark" ? "light" : "dark");
    });
});

document.querySelectorAll("[data-rule-select]").forEach((select) => {
    const target = document.getElementById(select.dataset.pointsTarget);
    const syncPoints = () => {
        if (!target) return;
        const option = select.options[select.selectedIndex];
        target.value = option?.dataset.points || "";
    };
    select.addEventListener("change", syncPoints);
    syncPoints();
});

document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
        if (!window.confirm(form.dataset.confirm)) {
            event.preventDefault();
        }
    });
});

const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
const sidebarClose = document.querySelector("[data-sidebar-close]");
const sidebarLinks = document.querySelectorAll(".side-nav a");

function setSidebar(open) {
    document.body.classList.toggle("sidebar-open", open);
}

sidebarToggle?.addEventListener("click", () => setSidebar(true));
sidebarClose?.addEventListener("click", () => setSidebar(false));
sidebarLinks.forEach((link) => link.addEventListener("click", () => setSidebar(false)));
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
        setSidebar(false);
    }
});

window.setTimeout(() => {
    document.querySelectorAll(".app-toast").forEach((toast) => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
    });
}, 3200);

function parseUtcDate(value) {
    if (!value) return null;
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
}

document.querySelectorAll("[data-countdown]").forEach((timer) => {
    const endAt = parseUtcDate(timer.dataset.endTime);
    const valueTarget = timer.querySelector("[data-countdown-value], .countdown-value, b") || timer;
    const tick = () => {
        if (!endAt) return;
        const remaining = Math.max(0, endAt.getTime() - Date.now());
        const hours = Math.floor(remaining / 3600000);
        const minutes = Math.floor((remaining % 3600000) / 60000);
        const seconds = Math.floor((remaining % 60000) / 1000);
        valueTarget.textContent = [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
        if (remaining <= 0) {
            document.querySelectorAll("[data-sprint-form] input, [data-sprint-form] button").forEach((field) => {
                field.disabled = true;
            });
            document.querySelectorAll(".status-pill").forEach((pill) => {
                pill.textContent = "Elite Sprint Closed";
            });
            window.clearInterval(interval);
            if (timer.dataset.reloadOnExpire === "true" && !window.sessionStorage.getItem(`sprint-expired-${timer.dataset.endTime}`)) {
                window.sessionStorage.setItem(`sprint-expired-${timer.dataset.endTime}`, "1");
                window.setTimeout(() => window.location.reload(), 1200);
            }
        }
    };
    const interval = window.setInterval(tick, 1000);
    tick();
});

document.querySelectorAll("[data-task-section]").forEach((section) => {
    const countInput = section.querySelector("[data-task-count]");
    const inputWrap = section.querySelector("[data-task-inputs]");
    const label = section.querySelector("legend")?.textContent || "Sprint";
    const renderInputs = () => {
        const count = Math.max(0, Math.min(parseInt(countInput.value || "0", 10) || 0, 100));
        const existing = Array.from(inputWrap.querySelectorAll("input")).map((input) => input.value);
        inputWrap.innerHTML = "";
        for (let index = 0; index < count; index += 1) {
            const input = document.createElement("input");
            input.type = "text";
            input.name = `${section.dataset.taskSection}_tasks`;
            input.placeholder = `${label} task ID ${index + 1}, e.g. TD001`;
            input.value = existing[index] || "";
            input.required = true;
            inputWrap.appendChild(input);
        }
    };
    countInput?.addEventListener("input", renderInputs);
    renderInputs();
});

const proofModal = document.getElementById("proofModal");
const proofModalBody = document.getElementById("proofModalBody");

document.querySelectorAll(".proof-preview").forEach((button) => {
    button.addEventListener("click", (event) => {
        event.preventDefault();
        const proofList = (button.dataset.proofList || "").split("|").filter(Boolean);
        const modal = new bootstrap.Modal(proofModal);

        if (!proofList.length) {
            proofModalBody.innerHTML = "<p class='text-white'>No proof file available.</p>";
            modal.show();
            return;
        }

        const slides = proofList.map((url) => {
            const normalized = url.trim();
            const lower = normalized.toLowerCase();
            if (lower.endsWith(".pdf")) {
                return `<div class="proof-slide"><iframe src="${normalized}" title="Proof preview" allow="fullscreen"></iframe></div>`;
            }
            return `<div class="proof-slide"><img src="${normalized}" alt="Proof preview"></div>`;
        }).join("");

        proofModalBody.innerHTML = `<div class="proof-gallery">${slides}</div>`;
        modal.show();
    });
});

const sprintTrendChart = document.getElementById("sprintTrendChart");
if (sprintTrendChart && window.Chart) {
    const labels = JSON.parse(sprintTrendChart.dataset.labels || "[]");
    const values = JSON.parse(sprintTrendChart.dataset.values || "[]");
    new Chart(sprintTrendChart, {
        type: "line",
        data: {
            labels,
            datasets: [{
                label: "Participants",
                data: values,
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.18)",
                tension: 0.35,
                fill: true,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        },
    });
}
