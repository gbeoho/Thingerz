(function() {
    'use strict';

    var navToggle = document.querySelector('.nav-toggle');
    var navLinks = document.querySelector('.nav-links');

    if (navToggle && navLinks) {
        navToggle.addEventListener('click', function(e) {
            e.stopPropagation();
            var isActive = navLinks.classList.toggle('active');
            document.body.style.overflow = isActive ? 'hidden' : '';
        });
        navLinks.querySelectorAll('a, button').forEach(function(el) {
            el.addEventListener('click', function() {
                navLinks.classList.remove('active');
                document.body.style.overflow = '';
            });
        });
        document.addEventListener('click', function(e) {
            if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    }

    var stickyCats = document.querySelector('.sticky-categories');
    if (stickyCats) {
        var chips = stickyCats.querySelectorAll('.sticky-cat-chip');
        chips.forEach(function(chip) {
            chip.addEventListener('click', function() {
                chips.forEach(function(c) { c.classList.remove('active'); });
                this.classList.add('active');
            });
        });
    }

    var videoCards = document.querySelectorAll('.video-card');
    videoCards.forEach(function(card) {
        card.addEventListener('mouseenter', function() {
            var stamp = card.querySelector('.card-stamp');
            if (stamp) {
                stamp.style.transform = 'rotate(' + (Math.random() * 6 - 3) + 'deg) scale(1.05)';
            }
        });
        card.addEventListener('mouseleave', function() {
            var stamp = card.querySelector('.card-stamp');
            if (stamp) {
                stamp.style.transform = 'rotate(2deg) scale(1)';
            }
        });
    });
})();
