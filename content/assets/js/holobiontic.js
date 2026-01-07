document.addEventListener('DOMContentLoaded', () => {
    const spores = document.querySelectorAll('.bio-spores span');
    const halo = document.querySelector('.bio-halo');
    
    // Mouse Interaction
    document.addEventListener('mousemove', (e) => {
        const x = e.clientX;
        const y = e.clientY;
        
        spores.forEach(spore => {
            const rect = spore.getBoundingClientRect();
            const sporeX = rect.left + rect.width / 2;
            const sporeY = rect.top + rect.height / 2;
            
            const dx = sporeX - x;
            const dy = sporeY - y;
            const dist = Math.sqrt(dx*dx + dy*dy);
            
            if (dist < 200) {
                const angle = Math.atan2(dy, dx);
                const force = (200 - dist) / 10;
                
                const moveX = Math.cos(angle) * force;
                const moveY = Math.sin(angle) * force;
                
                spore.style.transform = `translate(${moveX}px, ${moveY}px)`;
            } else {
                spore.style.transform = `translate(0, 0)`;
            }
        });
        
        // Halo Parallax
        if (halo) {
            const moveX = (x - window.innerWidth / 2) / 50;
            const moveY = (y - window.innerHeight / 2) / 50;
            halo.style.transform = `translate(calc(-50% + ${moveX}px), calc(-50% + ${moveY}px)) scale(1.1)`;
        }
    });
    
    // Scroll Breathing & Card Pulse
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.animation = 'organicPulse 2s ease-out forwards';
            }
        });
    }, { threshold: 0.2 });

    document.querySelectorAll('.card, .content-block').forEach(card => {
        observer.observe(card);
    });

    window.addEventListener('scroll', () => {
        const scrolled = window.scrollY;
        if (halo) {
            const scale = 1 + (scrolled * 0.0005);
            // We combine with the breathing animation in CSS
            // But JS override might conflict. Let's just adjust opacity.
            halo.style.opacity = Math.max(0.2, 0.8 - (scrolled * 0.001));
        }
    });
});
