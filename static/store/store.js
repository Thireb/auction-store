/* Auction Store storefront: small Alpine components. Load before Alpine (both deferred). */

(function () {
  "use strict";

  function rupees(n) {
    return "Rs " + Math.round(n).toLocaleString("en-US");
  }

  function csrf() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function reducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  document.addEventListener("alpine:init", function () {
    var Alpine = window.Alpine;

    /* A live countdown to a lot opening. Reloads the page when the lot opens. */
    Alpine.data("countdown", function (seconds) {
      return {
        end: Date.now() + seconds * 1000,
        left: seconds,
        timer: null,
        init: function () {
          var self = this;
          this.timer = setInterval(function () {
            self.left = Math.max(0, Math.round((self.end - Date.now()) / 1000));
            if (self.left === 0) {
              clearInterval(self.timer);
              window.location.reload();
            }
          }, 1000);
        },
        destroy: function () {
          clearInterval(this.timer);
        },
        pad: function (n) {
          return String(n).padStart(2, "0");
        },
        get days() { return Math.floor(this.left / 86400); },
        get hours() { return this.pad(Math.floor(this.left / 3600) % 24); },
        get minutes() { return this.pad(Math.floor(this.left / 60) % 60); },
        get secs() { return this.pad(this.left % 60); },
      };
    });

    /* The product page buy box: variant, quantity, live tier price. The server checks
       every price again; this only shows the customer what they will pay. */
    Alpine.data("buyBox", function () {
      var variants = JSON.parse(document.getElementById("variant-data").textContent);
      return {
        variants: variants,
        selected: 0,
        qty: variants.length ? variants[0].min_qty : 1,
        flip: 0,
        get v() { return this.variants[this.selected]; },
        get max() { return this.v.available === null ? 9999 : this.v.available; },
        get unit() {
          var price = this.v.price, qty = this.qty;
          this.v.tiers.forEach(function (t) { if (qty >= t.min && t.price < price) price = t.price; });
          return price;
        },
        get unitText() { return rupees(this.unit); },
        get saving() { return (this.v.price - this.unit) * this.qty; },
        get note() {
          if (this.saving > 0) return "each, you save " + rupees(this.saving);
          return this.qty > 1 ? "each" : "";
        },
        get rungs() {
          var self = this;
          var rows = [{ min: this.v.min_qty, price: this.v.price, wholesale: false }].concat(this.v.tiers);
          var active = rows.filter(function (r) { return self.qty >= r.min; }).sort(function (a, b) { return a.price - b.price; })[0];
          return rows.map(function (r) {
            return {
              key: r.min + "-" + r.wholesale,
              label: r.min + (r.wholesale ? "+ (wholesale)" : r === rows[0] && rows.length > 1 ? " to " + (rows[1].min - 1) : "+"),
              price: rupees(r.price) + " each",
              on: r === active,
            };
          });
        },
        pick: function (i) {
          this.selected = i;
          this.qty = this.v.min_qty;
          this.flip++;
        },
        inc: function () {
          if (this.qty + this.v.step <= this.max) { this.qty += this.v.step; this.flip++; }
        },
        dec: function () {
          if (this.qty - this.v.step >= this.v.min_qty) { this.qty -= this.v.step; this.flip++; }
        },
        fix: function () {
          var q = parseInt(this.qty, 10) || this.v.min_qty;
          q = Math.max(this.v.min_qty, Math.min(q, this.max));
          q -= (q - this.v.min_qty) % this.v.step;
          this.qty = q;
          this.flip++;
        },
      };
    });

    /* Dig mode: one piece at a time. Swipe or press right to save, left to skip. */
    Alpine.data("dig", function () {
      var data = JSON.parse(document.getElementById("dig-data").textContent);
      return {
        items: data.items,
        total: data.total,
        i: 0,
        dx: 0,
        drag: false,
        leaving: null,
        fresh: false,
        startX: 0,
        moved: false,
        shelf: data.items.filter(function (p) { return p.saved; }),
        get top() { return this.items[this.i]; },
        get next() { return this.items[this.i + 1]; },
        get done() { return this.i >= this.items.length; },
        get progress() { return Math.min(this.i + 1, this.items.length) + " of " + this.items.length; },
        get progressWidth() { return (100 * Math.min(this.i + 1, this.items.length) / Math.max(this.items.length, 1)) + "%"; },
        get lean() { return Math.max(-1, Math.min(1, this.dx / 110)); },
        get topStyle() {
          var t;
          if (this.leaving === "right") t = "translateX(130%) rotate(18deg)";
          else if (this.leaving === "left") t = "translateX(-130%) rotate(-18deg)";
          else t = "translateX(" + this.dx + "px) rotate(" + this.dx / 18 + "deg)";
          var move = this.drag || this.fresh || reducedMotion() ? "none" : "transform .34s cubic-bezier(.3,.7,.4,1)";
          return "transform:" + t + ";transition:" + move;
        },
        get nextStyle() {
          var t = this.leaving ? "none" : "translateY(14px) scale(.95)";
          var move = this.leaving && !reducedMotion() ? "transform .34s ease, opacity .34s ease" : "none";
          return "transform:" + t + ";opacity:" + (this.leaving ? 1 : 0.8) + ";transition:" + move;
        },
        get saveStamp() { return this.leaving === "right" ? 1 : Math.max(0, this.lean); },
        get skipStamp() { return this.leaving === "left" ? 1 : Math.max(0, -this.lean); },
        decide: function (dir) {
          if (this.leaving || this.done) return;
          var item = this.top, self = this;
          this.fresh = false;
          this.drag = false;
          this.leaving = dir;
          if (dir === "right" && !item.saved) {
            item.saved = true;
            this.shelf.push(item);
            this.save(item);
          }
          setTimeout(function () {
            self.i++;
            self.leaving = null;
            self.dx = 0;
            self.fresh = true;
          }, reducedMotion() ? 0 : 340);
        },
        save: function (item) {
          fetch(item.save_url, {
            method: "POST",
            headers: { "X-CSRFToken": csrf(), "HX-Request": "true" },
            credentials: "same-origin",
          }).then(function (r) { return r.ok ? r.text() : null; }).then(function () {
            var badge = document.getElementById("saved-count");
            if (badge) badge.textContent = String(parseInt(badge.textContent || "0", 10) + 1);
          });
        },
        down: function (e) {
          if (this.leaving || e.button > 0) return;
          this.startX = e.clientX;
          this.moved = false;
          this.drag = true;
          this.fresh = false;
          e.currentTarget.setPointerCapture(e.pointerId);
        },
        move: function (e) {
          if (!this.drag) return;
          this.dx = e.clientX - this.startX;
          if (Math.abs(this.dx) > 6) this.moved = true;
        },
        up: function () {
          if (!this.drag) return;
          if (this.dx > 100) this.decide("right");
          else if (this.dx < -100) this.decide("left");
          else { this.drag = false; this.dx = 0; }
        },
        open: function (e) {
          /* A tap opens the piece; a drag does not. */
          if (this.moved || this.leaving) e.preventDefault();
        },
        restart: function () {
          this.i = 0;
          this.fresh = true;
        },
      };
    });
  });
})();
