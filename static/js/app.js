// Shared frontend glue. Keep this tiny: templates attach these Alpine components
// directly where behavior is needed.

(function () {
  const PHOTOSWIPE_VERSION = "5.4.4";
  const PHOTOSWIPE_BASE_URL = `https://cdn.jsdelivr.net/npm/photoswipe@${PHOTOSWIPE_VERSION}/dist`;

  window.app = window.app || {};

  document.addEventListener("alpine:init", () => {
    Alpine.data("copySource", () => ({
      copied: false,
      message: "Copied",
      timeout: null,

      async copy(url) {
        clearTimeout(this.timeout);

        try {
          await navigator.clipboard.writeText(url);
          this.message = "Copied";
        } catch (_error) {
          this.message = "Copy failed";
        }

        this.copied = true;
        this.timeout = setTimeout(() => {
          this.copied = false;
        }, 1400);
      },

      destroy() {
        clearTimeout(this.timeout);
      },
    }));

    Alpine.data("likeButton", ({ liked }) => ({
      liked,

      toggle() {
        this.liked = !this.liked;
      },
    }));

    Alpine.data("photoSwipeGallery", () => ({
      lightbox: null,
      loading: null,
      pendingOpen: null,
      earlyClickHandler: null,

      async init() {
        if (this.lightbox || this.loading) return this.loading;

        this.earlyClickHandler = (event) => {
          const link = event.target.closest("a[data-pswp-width]");
          if (!link || !this.$el.contains(link) || this.lightbox) return;

          event.preventDefault();

          const links = Array.from(this.$el.querySelectorAll("a[data-pswp-width]"));
          this.pendingOpen = {
            href: link.href,
            index: links.indexOf(link),
            point: { x: event.clientX, y: event.clientY },
          };

          this.loading?.then(() => this.openPending()).catch(() => {
            if (this.pendingOpen?.href) window.location.assign(this.pendingOpen.href);
          });
        };

        this.$el.addEventListener("click", this.earlyClickHandler, true);

        this.loading = this.setupLightbox();
        return this.loading;
      },

      async setupLightbox() {
        try {
          const { default: PhotoSwipeLightbox } = await import(
            `${PHOTOSWIPE_BASE_URL}/photoswipe-lightbox.esm.js`
          );

          this.lightbox = new PhotoSwipeLightbox({
            gallery: this.$el,
            children: "a[data-pswp-width]",
            paddingFn: (viewportSize) => ({
              top: viewportSize.y * 0.05,
              right: viewportSize.x * 0.05,
              bottom: viewportSize.y * 0.05,
              left: viewportSize.x * 0.05,
            }),
            pswpModule: () => import(`${PHOTOSWIPE_BASE_URL}/photoswipe.esm.js`),
          });

          this.lightbox.on("uiRegister", () => {
            this.lightbox.pswp.ui.registerElement({
              name: "custom-caption",
              order: 9,
              isButton: false,
              appendTo: "root",
              html: "",
              onInit: (caption, pswp) => {
                const updateCaption = () => {
                  const link = pswp.currSlide?.data?.element;
                  caption.textContent =
                    link?.dataset.pswpCaption || link?.querySelector("img")?.alt || "";
                };

                pswp.on("change", updateCaption);
                updateCaption();
              },
            });
          });

          this.lightbox.init();
          this.openPending();
        } catch (error) {
          console.warn("PhotoSwipe failed to load; falling back to image links.", error);
          throw error;
        }
      },

      openPending() {
        if (!this.lightbox || !this.pendingOpen || this.pendingOpen.index < 0) return;

        const { index, point } = this.pendingOpen;
        this.pendingOpen = null;
        this.lightbox.loadAndOpen(index, { gallery: this.$el }, point);
      },

      destroy() {
        if (this.earlyClickHandler) {
          this.$el.removeEventListener("click", this.earlyClickHandler, true);
        }

        this.lightbox?.destroy();
        this.lightbox = null;
        this.loading = null;
        this.pendingOpen = null;
        this.earlyClickHandler = null;
      },
    }));
  });

  document.body.addEventListener("showMessage", (evt) => {
    const detail = evt.detail || {};
    console.info("[flash]", detail.level || "info", detail.message || detail);
  });
})();
