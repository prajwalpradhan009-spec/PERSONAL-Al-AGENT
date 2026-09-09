/**
 * 3D Neural Particle Orb & Audio Waveform Visualizer
 * Renders an interactive 3D particle sphere responding to agent states & audio frequencies.
 */

class NeuralOrbVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.particleCount = 420;
        this.baseRadius = 140;
        this.radius = this.baseRadius;
        this.state = 'idle'; // idle | listening | thinking | executing | speaking
        
        // 3D Rotation Angles
        this.rotX = 0;
        this.rotY = 0;
        this.rotZ = 0;
        this.speedX = 0.003;
        this.speedY = 0.005;
        this.targetSpeedMultiplier = 1.0;
        this.currentSpeedMultiplier = 1.0;
        
        // Mouse & Interaction
        this.mouse = { x: 0, y: 0, isHovered: false, targetX: 0, targetY: 0 };
        this.shockwave = { radius: 0, active: false, maxRadius: 280, alpha: 1 };
        
        // Audio Frequency Data (0 - 255)
        this.audioData = new Uint8Array(64);
        this.audioAverage = 0;
        
        // Animation Loop
        this.time = 0;
        this.initCanvas();
        this.initParticles();
        this.bindEvents();
        this.animate = this.animate.bind(this);
        requestAnimationFrame(this.animate);
    }

    initCanvas() {
        this.resize();
        window.addEventListener('resize', () => this.resize());
    }

    resize() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.dpr = window.devicePixelRatio || 1;
        this.width = rect.width;
        this.height = rect.height;
        this.canvas.width = this.width * this.dpr;
        this.canvas.height = this.height * this.dpr;
        this.ctx.scale(this.dpr, this.dpr);
        this.cx = this.width / 2;
        this.cy = this.height / 2;
        this.baseRadius = Math.min(this.width, this.height) * 0.28;
    }

    initParticles() {
        this.particles = [];
        for (let i = 0; i < this.particleCount; i++) {
            // Fibonacci sphere distribution
            const phi = Math.acos(1 - 2 * (i + 0.5) / this.particleCount);
            const theta = Math.PI * (1 + Math.sqrt(5)) * i;
            
            const x = Math.sin(phi) * Math.cos(theta);
            const y = Math.sin(phi) * Math.sin(theta);
            const z = Math.cos(phi);
            
            this.particles.push({
                x, y, z,
                baseX: x, baseY: y, baseZ: z,
                size: Math.random() * 2.2 + 1.2,
                noiseOffset: Math.random() * 100,
                colorShift: Math.random(),
                pulseSpeed: 0.02 + Math.random() * 0.03
            });
        }
    }

    bindEvents() {
        this.canvas.addEventListener('mousemove', (e) => {
            const rect = this.canvas.getBoundingClientRect();
            this.mouse.targetX = (e.clientX - rect.left - this.cx) / (this.width / 2);
            this.mouse.targetY = (e.clientY - rect.top - this.cy) / (this.height / 2);
            this.mouse.isHovered = true;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.mouse.targetX = 0;
            this.mouse.targetY = 0;
            this.mouse.isHovered = false;
        });

        this.canvas.addEventListener('click', () => {
            this.triggerShockwave();
        });
    }

    triggerShockwave() {
        this.shockwave.radius = this.baseRadius * 0.4;
        this.shockwave.active = true;
        this.shockwave.alpha = 1.0;
    }

    setState(newState) {
        if (this.state === newState) return;
        this.state = newState;
        
        switch (newState) {
            case 'listening':
                this.targetSpeedMultiplier = 1.4;
                break;
            case 'thinking':
                this.targetSpeedMultiplier = 3.5;
                break;
            case 'executing':
                this.targetSpeedMultiplier = 2.2;
                break;
            case 'speaking':
                this.targetSpeedMultiplier = 1.8;
                break;
            case 'idle':
            default:
                this.targetSpeedMultiplier = 1.0;
                break;
        }
    }

    setAudioFrequencyData(dataArray) {
        if (!dataArray || dataArray.length === 0) return;
        this.audioData = dataArray;
        let sum = 0;
        for (let i = 0; i < Math.min(dataArray.length, 32); i++) {
            sum += dataArray[i];
        }
        this.audioAverage = sum / 32;
    }

    animate() {
        this.time += 0.02;
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        // Smooth speed transition
        this.currentSpeedMultiplier += (this.targetSpeedMultiplier - this.currentSpeedMultiplier) * 0.08;
        
        // Smooth mouse tilt
        this.mouse.x += (this.mouse.targetX - this.mouse.x) * 0.05;
        this.mouse.y += (this.mouse.targetY - this.mouse.y) * 0.05;
        
        this.rotY += this.speedY * this.currentSpeedMultiplier + this.mouse.x * 0.01;
        this.rotX += this.speedX * this.currentSpeedMultiplier + this.mouse.y * 0.01;
        this.rotZ += 0.001 * this.currentSpeedMultiplier;
        
        // Breathing radius pulsation
        const audioBoost = (this.audioAverage / 255) * 45;
        const breath = Math.sin(this.time * 2) * 6;
        this.radius = this.baseRadius + breath + audioBoost;
        
        // Draw Core Ambient Glow & Reticles
        this.drawCoreGlow();
        
        // Project & Render 3D Particles
        this.renderParticles();
        
        // Render Waveform Rings / Shockwaves
        this.renderShockwave();
        
        requestAnimationFrame(this.animate);
    }

    drawCoreGlow() {
        const grad = this.ctx.createRadialGradient(this.cx, this.cy, 0, this.cx, this.cy, this.radius * 1.3);
        
        let c1, c2;
        if (this.state === 'listening') {
            c1 = 'rgba(16, 185, 129, 0.28)';
            c2 = 'rgba(16, 185, 129, 0.0)';
        } else if (this.state === 'thinking') {
            c1 = 'rgba(168, 85, 247, 0.35)';
            c2 = 'rgba(168, 85, 247, 0.0)';
        } else if (this.state === 'executing') {
            c1 = 'rgba(245, 158, 11, 0.32)';
            c2 = 'rgba(245, 158, 11, 0.0)';
        } else if (this.state === 'speaking') {
            c1 = 'rgba(0, 240, 255, 0.4)';
            c2 = 'rgba(0, 136, 255, 0.0)';
        } else {
            // Idle
            c1 = 'rgba(0, 240, 255, 0.18)';
            c2 = 'rgba(168, 85, 247, 0.0)';
        }
        
        grad.addColorStop(0, c1);
        grad.addColorStop(1, c2);
        
        this.ctx.fillStyle = grad;
        this.ctx.beginPath();
        this.ctx.arc(this.cx, this.cy, this.radius * 1.4, 0, Math.PI * 2);
        this.ctx.fill();
    }

    renderParticles() {
        const cosY = Math.cos(this.rotY);
        const sinY = Math.sin(this.rotY);
        const cosX = Math.cos(this.rotX);
        const sinX = Math.sin(this.rotX);
        const cosZ = Math.cos(this.rotZ);
        const sinZ = Math.sin(this.rotZ);

        const fov = 400;
        const projected = [];

        for (let i = 0; i < this.particles.length; i++) {
            const p = this.particles[i];
            
            // Dynamic radial displacement based on state & audio
            let rMod = this.radius;
            if (this.state === 'listening') {
                const freqIndex = i % 32;
                const freqVal = this.audioData[freqIndex] || 0;
                rMod += (freqVal / 255) * 35;
            } else if (this.state === 'thinking') {
                const vortex = Math.sin(this.time * 6 + p.noiseOffset) * 14;
                rMod += vortex;
            } else if (this.state === 'speaking') {
                const wave = Math.sin(this.time * 5 + p.y * 4) * 16;
                rMod += wave + (this.audioAverage / 255) * 20;
            }
            
            let x = p.baseX * rMod;
            let y = p.baseY * rMod;
            let z = p.baseZ * rMod;
            
            // 3D Rotations
            // Y-axis
            let x1 = x * cosY - z * sinY;
            let z1 = z * cosY + x * sinY;
            // X-axis
            let y2 = y * cosX - z1 * sinX;
            let z2 = z1 * cosX + y * sinX;
            // Z-axis
            let x3 = x1 * cosZ - y2 * sinZ;
            let y3 = y2 * cosZ + x1 * sinZ;
            
            // Perspective projection
            const scale = fov / (fov + z2 + 100);
            const projX = this.cx + x3 * scale;
            const projY = this.cy + y3 * scale;
            const alpha = Math.max(0.15, Math.min(1.0, (z2 + this.radius) / (2 * this.radius)));
            
            projected.push({
                x: projX,
                y: projY,
                z: z2,
                scale,
                alpha,
                size: p.size * scale,
                colorShift: p.colorShift
            });
        }

        // Sort by Z for correct depth rendering
        projected.sort((a, b) => a.z - b.z);

        // Render Particles & Inter-connecting Synapse lines
        for (let i = 0; i < projected.length; i++) {
            const pt = projected[i];
            
            let color;
            if (this.state === 'listening') {
                color = `rgba(16, 245, 160, ${pt.alpha * 0.9})`;
            } else if (this.state === 'thinking') {
                color = pt.colorShift > 0.5 ? `rgba(168, 85, 247, ${pt.alpha})` : `rgba(236, 72, 153, ${pt.alpha})`;
            } else if (this.state === 'executing') {
                color = pt.colorShift > 0.5 ? `rgba(245, 158, 11, ${pt.alpha})` : `rgba(251, 191, 36, ${pt.alpha})`;
            } else if (this.state === 'speaking') {
                color = pt.colorShift > 0.5 ? `rgba(0, 240, 255, ${pt.alpha})` : `rgba(255, 255, 255, ${pt.alpha})`;
            } else {
                // Idle
                color = pt.colorShift > 0.6 ? `rgba(0, 240, 255, ${pt.alpha})` : `rgba(138, 43, 226, ${pt.alpha * 0.8})`;
            }
            
            this.ctx.fillStyle = color;
            this.ctx.beginPath();
            this.ctx.arc(pt.x, pt.y, Math.max(0.8, pt.size), 0, Math.PI * 2);
            this.ctx.fill();
            
            // Connect nearby points in foreground
            if (pt.z > 20 && i % 3 === 0 && i < projected.length - 1) {
                const nextPt = projected[i + 1];
                const dist = Math.hypot(pt.x - nextPt.x, pt.y - nextPt.y);
                if (dist < 45) {
                    this.ctx.strokeStyle = `rgba(0, 240, 255, ${pt.alpha * 0.25})`;
                    this.ctx.lineWidth = 0.6;
                    this.ctx.beginPath();
                    this.ctx.moveTo(pt.x, pt.y);
                    this.ctx.lineTo(nextPt.x, nextPt.y);
                    this.ctx.stroke();
                }
            }
        }
    }

    renderShockwave() {
        if (!this.shockwave.active) return;
        
        this.shockwave.radius += 5.5;
        this.shockwave.alpha *= 0.94;
        
        this.ctx.save();
        this.ctx.strokeStyle = `rgba(0, 240, 255, ${this.shockwave.alpha})`;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.arc(this.cx, this.cy, this.shockwave.radius, 0, Math.PI * 2);
        this.ctx.stroke();
        this.ctx.restore();
        
        if (this.shockwave.alpha < 0.02 || this.shockwave.radius > this.shockwave.maxRadius) {
            this.shockwave.active = false;
        }
    }
}

window.NeuralOrbVisualizer = NeuralOrbVisualizer;

