/* ═══════════════════════════════════════════════════════════════════════
   Nexa Language — Global JavaScript
   Features: Particle Starfield, Scroll Reveal, Navigation, Copy
   ═══════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── Particle Starfield ── */
  const canvas = document.getElementById('particles-canvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    let particles = [];
    let mouseX = 0, mouseY = 0;
    let width, height;

    function resize() {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    }

    class Particle {
      constructor() {
        this.reset();
        this.y = Math.random() * height;
      }

      reset() {
        this.x = Math.random() * width;
        this.y = -10;
        this.z = Math.random() * 0.8 + 0.2; // depth: 0.2 ~ 1.0
        this.size = this.z * 2.5 + 0.5;
        this.speed = this.z * 0.4 + 0.15;
        this.opacity = this.z * 0.5 + 0.2;
        this.twinkleSpeed = Math.random() * 0.02 + 0.005;
        this.twinkleOffset = Math.random() * Math.PI * 2;
      }

      update() {
        this.y += this.speed;
        // Slight horizontal drift toward mouse
        const dx = (mouseX - width / 2) / (width / 2);
        this.x += dx * this.speed * 0.3;

        if (this.y > height + 10) {
          this.reset();
        }
        if (this.x < -10) this.x = width + 10;
        if (this.x > width + 10) this.x = -10;
      }

      draw(ctx, frame) {
        const twinkle = Math.sin(frame * this.twinkleSpeed + this.twinkleOffset) * 0.3 + 0.7;
        const alpha = this.opacity * twinkle;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(160, 140, 240, ${alpha})`;
        ctx.fill();

        // Glow for larger particles
        if (this.size > 2) {
          ctx.beginPath();
          ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(108, 92, 231, ${alpha * 0.15})`;
          ctx.fill();
        }
      }
    }

    function initParticles() {
      resize();
      const count = Math.min(Math.floor((width * height) / 8000), 200);
      particles = Array.from({ length: count }, () => new Particle());
    }

    let frame = 0;
    function animate() {
      frame++;
      ctx.clearRect(0, 0, width, height);

      // Subtle gradient overlay
      const grad = ctx.createRadialGradient(
        width / 2, height / 2, 0,
        width / 2, height / 2, Math.max(width, height) * 0.7
      );
      grad.addColorStop(0, 'rgba(10, 10, 26, 0)');
      grad.addColorStop(1, 'rgba(6, 6, 15, 0.6)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);

      particles.forEach(p => {
        p.update();
        p.draw(ctx, frame);
      });

      requestAnimationFrame(animate);
    }

    window.addEventListener('resize', initParticles);
    window.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    });

    initParticles();
    animate();
  }

  /* ── Scroll Reveal ── */
  const revealElements = document.querySelectorAll('.reveal');

  function checkReveal() {
    const windowHeight = window.innerHeight;
    revealElements.forEach(el => {
      const rect = el.getBoundingClientRect();
      const revealPoint = 100;
      if (rect.top < windowHeight - revealPoint) {
        el.classList.add('visible');
      }
    });
  }

  if (revealElements.length > 0) {
    window.addEventListener('scroll', checkReveal, { passive: true });
    checkReveal(); // initial check
  }

  /* ── Navigation ── */
  const nav = document.querySelector('.nav');
  const navToggle = document.querySelector('.nav-toggle');
  const navLinks = document.querySelector('.nav-links');

  // Scroll effect
  if (nav) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 50) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    }, { passive: true });
  }

  // Mobile toggle
  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      navLinks.classList.toggle('open');
      const spans = navToggle.querySelectorAll('span');
      if (navLinks.classList.contains('open')) {
        spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
        spans[1].style.opacity = '0';
        spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
      } else {
        spans[0].style.transform = '';
        spans[1].style.opacity = '';
        spans[2].style.transform = '';
      }
    });

    // Close on link click
    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navLinks.classList.remove('open');
        const spans = navToggle.querySelectorAll('span');
        spans[0].style.transform = '';
        spans[1].style.opacity = '';
        spans[2].style.transform = '';
      });
    });
  }

  /* ── Copy to Clipboard ── */
  const copyBtn = document.querySelector('.copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const cmd = copyBtn.parentElement.textContent.replace('Copy', '').trim();
      navigator.clipboard.writeText(cmd).then(() => {
        copyBtn.textContent = 'Copied!';
        setTimeout(() => {
          copyBtn.textContent = 'Copy';
        }, 2000);
      }).catch(() => {
        copyBtn.textContent = 'Failed';
        setTimeout(() => {
          copyBtn.textContent = 'Copy';
        }, 2000);
      });
    });
  }

  /* ── Smooth scroll for anchor links ── */
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      const target = document.querySelector(this.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

})();