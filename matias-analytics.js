/**
 * M.A.T.I.A.S. Analytics — Tracking script for the website.
 * Include this script on every page to send page views and click events
 * to the Matias Seek API (Render).
 *
 * Usage: add this BEFORE closing </body> tag:
 *   <script src="/matias-analytics.js"></script>
 *
 * Or configure the API base inline:
 *   <script>window.MATIAS_API_BASE = "https://matias-api-ka16.onrender.com";</script>
 *   <script src="/matias-analytics.js"></script>
 */
(function () {
  const API = (window.MATIAS_API_BASE || "https://matias-api-ka16.onrender.com").replace(/\/+$/, "");

  function getSid() {
    let sid = localStorage.getItem("_matias_sid");
    if (!sid) {
      sid = "web-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);
      localStorage.setItem("_matias_sid", sid);
    }
    return sid;
  }

  function send(endpoint, body) {
    try {
      fetch(API + endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        keepalive: true,
      }).catch(function () {});
    } catch (e) {}
  }

  var sid = getSid();

  // ── Page view ────────────────────────────────────────
  send("/api/analytics/pageview", {
    session_id: sid,
    url: window.location.pathname + window.location.search,
    referrer: document.referrer || "",
  });

  // ── CTA click tracking ───────────────────────────────
  document.addEventListener("click", function (e) {
    var el = e.target.closest("a");
    if (!el) return;
    var href = el.getAttribute("href") || "";
    var text = (el.textContent || "").trim().slice(0, 120);
    var eventType = "link_click";
    var element = text || href.slice(0, 80);

    if (href.includes("calendar.app.google")) eventType = "demo_click";
    else if (href.includes("wa.me") || href.includes("whatsapp")) eventType = "whatsapp_click";
    else if (href.includes("mailto:") || href.includes("hola@akaike") || href.includes("oscar@akaike"))
      eventType = "email_click";

    send("/api/analytics/event", {
      session_id: sid,
      event_type: eventType,
      element: element,
      url: href.slice(0, 500),
    });
  });
})();
