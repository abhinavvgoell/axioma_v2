const samples = {
  checkout: {
    file: "checkout.ts",
    lines: [
      '<span class="tok-kw">import</span> { db } <span class="tok-kw">from</span> <span class="tok-str">\'@/lib/db\'</span>;',
      "",
      '<span class="tok-kw">export async function</span> <span class="tok-fn">checkout</span>(req) {',
      '  <span class="tok-kw">const</span> { userId, items } = req.body;',
      '  <span class="tok-kw">const</span> user = <span class="tok-kw">await</span> db.user.findUnique({',
      "    where: { id: userId }",
      "  });",
      "",
      '  <span class="tok-kw">const</span> total = items.reduce((sum, item) =&gt;',
      '    sum + item.price * item.quantity, <span class="tok-num">0</span>);',
      "",
      '  <span class="tok-kw">return</span> createOrder(user.id, total);',
      "}",
    ],
    findings: [
      { type: "SECURITY", level: "HIGH", title: "Untrusted price input", copy: "The total uses a client-supplied price. A modified request could change the amount charged.", location: "checkout.ts · line 10", tone: "high" },
      { type: "RELIABILITY", level: "MEDIUM", title: "Missing user guard", copy: "If the lookup returns no user, reading user.id will fail before the order is created.", location: "checkout.ts · line 12", tone: "medium" },
      { type: "EXAMPLES", level: "PASSED", title: "6 example checks passed", copy: "Configured examples passed. Generated and property checks were not run in this preview.", location: "6 cases · illustrative", tone: "medium" },
    ],
  },
  products: {
    file: "products.ts",
    lines: [
      '<span class="tok-kw">import</span> { db } <span class="tok-kw">from</span> <span class="tok-str">\'@/lib/db\'</span>;',
      "",
      '<span class="tok-kw">export async function</span> <span class="tok-fn">listProducts</span>(query) {',
      '  <span class="tok-kw">const</span> page = Number(query.page ?? <span class="tok-num">1</span>);',
      '  <span class="tok-kw">const</span> size = Number(query.size ?? <span class="tok-num">24</span>);',
      "",
      '  <span class="tok-kw">return</span> db.product.findMany({',
      '    skip: (page - <span class="tok-num">1</span>) * size,',
      "    take: size,",
      '    orderBy: { createdAt: <span class="tok-str">\'desc\'</span> },',
      "  });",
      "}",
    ],
    findings: [
      { type: "RELIABILITY", level: "MEDIUM", title: "Unbounded page size", copy: "A large query.size can request an expensive database read. Consider applying an upper bound.", location: "products.ts · line 5", tone: "medium" },
      { type: "CORRECTNESS", level: "REVIEW", title: "Non-numeric page value", copy: "Number() can produce NaN. Validate query values before building the database query.", location: "products.ts · line 4", tone: "high" },
      { type: "EXAMPLES", level: "PASSED", title: "4 example checks passed", copy: "Configured examples pass. Boundary behavior still needs a dedicated check.", location: "4 cases · illustrative", tone: "medium" },
    ],
  },
};

const canvas = document.querySelector("#vortex");
const ctx = canvas.getContext("2d");
const hero = document.querySelector(".hero");
let width = 0;
let height = 0;
let pixelRatio = 1;
let frameId = 0;
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function resizeCanvas() {
  const rect = hero.getBoundingClientRect();
  width = rect.width;
  height = rect.height;
  pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
  canvas.width = Math.round(width * pixelRatio);
  canvas.height = Math.round(height * pixelRatio);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
  drawVortex(0);
}

function drawVortex(time) {
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#080808";
  ctx.fillRect(0, 0, width, height);

  const centerX = width * 0.265;
  const centerY = height * 0.57;
  const maxRadius = Math.hypot(width * 0.88, height * 0.72);
  const lineCount = width < 640 ? 92 : 166;
  const motion = reduceMotion ? 0 : time * 0.000025;

  const glow = ctx.createRadialGradient(centerX, centerY, 3, centerX, centerY, maxRadius * 0.86);
  glow.addColorStop(0, "rgba(235,238,238,.13)");
  glow.addColorStop(.22, "rgba(164,171,173,.075)");
  glow.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  for (let line = 0; line < lineCount; line += 1) {
    const seed = (line / lineCount) * Math.PI * 2;
    const drift = Math.sin(seed * 4 + motion) * 0.012;
    const alpha = 0.045 + ((line * 37) % 11) * 0.008;
    ctx.beginPath();
    for (let step = 0; step <= 92; step += 1) {
      const t = step / 92;
      const radius = maxRadius * (1 - t) + 2.5;
      const angle = seed + 1.28 * Math.log(maxRadius / radius) + drift + motion;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius * 0.77;
      if (step === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(235,238,237,${alpha})`;
    ctx.lineWidth = line % 9 === 0 ? 1.15 : 0.7;
    ctx.stroke();
  }

  for (let dot = 0; dot < 90; dot += 1) {
    const seed = ((dot * 71) % 90) / 90 * Math.PI * 2;
    const t = ((dot * 29) % 90) / 90;
    const radius = maxRadius * (1 - t) + 4;
    const angle = seed + 1.28 * Math.log(maxRadius / radius) + motion;
    const x = centerX + Math.cos(angle) * radius;
    const y = centerY + Math.sin(angle) * radius * 0.77;
    const size = dot % 13 === 0 ? 1.8 : 0.8;
    ctx.fillStyle = `rgba(245,246,244,${dot % 7 === 0 ? 0.6 : 0.25})`;
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
  }

  if (!reduceMotion) frameId = window.requestAnimationFrame(drawVortex);
}

const sourceCode = document.querySelector("#source-code");
const fileName = document.querySelector("#file-name");
const reviewContent = document.querySelector("#review-content");
let activeSample = "checkout";

function renderFindings(findings) {
  reviewContent.innerHTML = findings.map((finding) => `
    <article class="finding">
      <div class="finding-meta">${finding.type} &nbsp;·&nbsp; <span class="${finding.tone}">${finding.level}</span></div>
      <h4 class="finding-title">${finding.title}</h4>
      <p class="finding-copy">${finding.copy}</p>
      <div class="finding-location">${finding.location}</div>
    </article>`).join("");
}

function renderSample(name) {
  activeSample = name;
  const sample = samples[name] ?? samples.checkout;
  fileName.textContent = sample.file;
  sourceCode.innerHTML = sample.lines.map((line, index) =>
    `<span class="code-row"><span class="line-number">${String(index + 1).padStart(2, "0")}</span>${line || " "}</span>`,
  ).join("");
  document.querySelectorAll(".tree-file[data-sample]").forEach((button) => {
    const selected = button.dataset.sample === name;
    button.classList.toggle("selected", selected);
    button.setAttribute("aria-current", selected ? "page" : "false");
  });
  renderFindings(sample.findings);
  document.querySelectorAll(".review-tab").forEach((tab) => {
    const selected = tab.dataset.view === "findings";
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
  });
}

function renderEvidence() {
  const rows = [
    ["EXAMPLE CASES", "6 / 6", ""],
    ["GENERATED INPUTS", "NOT RUN", "warn"],
    ["PROPERTY CHECKS", "NOT CONFIGURED", "off"],
    ["STATIC REVIEW", "LOW CONFIDENCE", "warn"],
    ["COMPLEXITY SIGNAL", "O(n) · HEURISTIC", "warn"],
    ["REFERENCE CHECK", "NOT CONFIGURED", "off"],
  ];
  reviewContent.innerHTML = `${rows.map(([label, value, state]) => `
    <div class="evidence-row"><i class="evidence-dot ${state}"></i><span>${label}</span><b>${value}</b></div>`).join("")}
    <p class="evidence-note">Sample values show how method and confidence can be presented. No checks have been run.</p>`;
}

document.querySelectorAll(".tree-file[data-sample]").forEach((button) => {
  button.addEventListener("click", () => renderSample(button.dataset.sample));
});

document.querySelectorAll(".review-tab").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".review-tab").forEach((tab) => {
      const selected = tab === button;
      tab.classList.toggle("active", selected);
      tab.setAttribute("aria-selected", String(selected));
    });
    if (button.dataset.view === "evidence") renderEvidence();
    else renderFindings(samples[activeSample].findings);
  });
});

document.querySelector("#run-preview").addEventListener("click", (event) => {
  const button = event.currentTarget;
  if (button.dataset.busy === "true") return;
  button.dataset.busy = "true";
  button.innerHTML = "<span>…</span> LOADING SAMPLE";
  window.setTimeout(() => {
    button.innerHTML = "<span>✓</span> SAMPLE READY";
    button.dataset.busy = "false";
    window.setTimeout(() => { button.innerHTML = "<span>▶</span> RUN SAMPLE REVIEW"; }, 1300);
  }, 650);
});

const heroTitle = document.querySelector(".hero-title");
const glitchWord = document.querySelector(".glitch-word");
window.addEventListener("pointermove", (event) => {
  const rect = glitchWord.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const dx = event.clientX - centerX;
  const dy = event.clientY - centerY;
  const outsideX = Math.max(rect.left - event.clientX, 0, event.clientX - rect.right);
  const outsideY = Math.max(rect.top - event.clientY, 0, event.clientY - rect.bottom);
  const distance = Math.hypot(outsideX, outsideY);
  const strength = Math.max(0, 1 - distance / 150);
  glitchWord.style.setProperty("--glitch-x", `${dx * strength * 0.01}px`);
  glitchWord.style.setProperty("--glitch-y", `${dy * strength * 0.01}px`);
  heroTitle.classList.toggle("is-glitching", strength > 0);
}, { passive: true });
window.addEventListener("pointerleave", () => {
  heroTitle.classList.remove("is-glitching");
  glitchWord.style.setProperty("--glitch-x", "0px");
  glitchWord.style.setProperty("--glitch-y", "0px");
});

if ("IntersectionObserver" in window && !reduceMotion) {
  const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
      observer.unobserve(entry.target);
    }
  }), { threshold: .12 });
  document.querySelectorAll(".approach, .service-row, .work-section, .closing").forEach((element) => {
    element.classList.add("reveal");
    observer.observe(element);
  });
}

window.addEventListener("resize", () => {
  window.cancelAnimationFrame(frameId);
  resizeCanvas();
});
resizeCanvas();
renderSample(activeSample);
