"use client";

import React, { useEffect, useRef, useState, useMemo } from 'react';
import { AnimatePresence } from 'framer-motion';
import { CONFIG } from '@/lib/config';
import { useTheme } from '@/context/ThemeContext';
import { Compass } from 'lucide-react';

import { StarNode, TransformState } from './galaxy-map/types';
import { 
  getProjectedCoords, 
  ROOM_COLORS_DARK, 
  ROOM_COLORS_LIGHT,
} from './galaxy-map/constants';

import ControlHub from './galaxy-map/ControlHub';
import InspectorPanel from './galaxy-map/InspectorPanel';
import HoverPanel from './galaxy-map/HoverPanel';
import SwarmLegend from './galaxy-map/SwarmLegend';

export default function GalaxyMap() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState<StarNode[]>([]);
  const [hovered, setHovered] = useState<StarNode | null>(null);
  const [selectedNode, setSelectedNode] = useState<StarNode | null>(null);
  const [transform, setTransform] = useState<TransformState>({ x: 0, y: 0, scale: 0.8 });
  const [isDragging, setIsDragging] = useState(false);
  const [lastMouse, setLastMouse] = useState({ x: 0, y: 0 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [showConnections, setShowConnections] = useState(true);
  
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const mouseDownPos = useRef({ x: 0, y: 0 });
  const pulseOffsetsRef = useRef<Record<string, number>>({});
  
  // 🏛️ Smooth Transform Glide Animation Tracker
  const glideAnimationRef = useRef<number | null>(null);

  // 🏛️ Offscreen canvas for pre-rendering stars to achieve massive frame-rate improvements
  const starsCanvasRef = useRef<HTMLCanvasElement | null>(null);

  // Generate background stars coordinate topology once to prevent random flickering
  const backgroundStars = useMemo(() => {
    const seededRandom = (s: number) => {
      const x = Math.sin(s) * 10000;
      return x - Math.floor(x);
    };
    return Array.from({ length: 1500 }, (_, i) => ({
      x: (seededRandom(i * 4 + 1) - 0.5) * 4000,
      y: (seededRandom(i * 4 + 2) - 0.5) * 4000,
      size: seededRandom(i * 4 + 3) * 0.9 + 0.1,
      opacityMult: seededRandom(i * 4 + 4)
    }));
  }, []);

  useEffect(() => {
    setMounted(true);
    let retryCount = 0;
    const maxRetries = 5;
    
    const fetchMap = async () => {
      try {
        const res = await fetch(`${CONFIG.API_BASE}/api/v1/topology/map`);
        if (!res.ok) {
          const text = await res.text();
          throw new Error(`FETCH_FAIL: ${res.status} ${res.statusText} - ${text.substring(0, 150)}`);
        }
        const nodes = JSON.parse(await res.text());
        if (Array.isArray(nodes)) {
          setData(nodes);
        }
      } catch (e) {
        console.error("Galaxy Fetch Error:", e);
        if (retryCount < maxRetries) {
          retryCount++;
          setTimeout(fetchMap, retryCount * 2000);
        }
      }
    };
    fetchMap();

    return () => {
      if (glideAnimationRef.current !== null) {
        cancelAnimationFrame(glideAnimationRef.current);
      }
    };
  }, []);

  // Pre-calculate pulse offsets to avoid high-frequency string parsing during draw calls
  useEffect(() => {
    const offsets: Record<string, number> = {};
    data.forEach(node => {
      offsets[node.id] = parseInt(node.id.slice(-2), 16) || node.id.charCodeAt(node.id.length - 1) || 0;
    });
    pulseOffsetsRef.current = offsets;
  }, [data]);

  // Listen to native OS Fullscreen changes to keep React state in perfect sync
  useEffect(() => {
    const handleFullscreenChange = () => {
      const container = canvasRef.current?.parentElement;
      if (!container) return;
      const doc = document as Document & { webkitFullscreenElement?: Element; mozFullScreenElement?: Element; msFullscreenElement?: Element };
      const isCurrentlyFullscreen = 
        doc.fullscreenElement === container || 
        doc.webkitFullscreenElement === container ||
        doc.mozFullScreenElement === container ||
        doc.msFullscreenElement === container;
      
      setIsFullscreen(!!isCurrentlyFullscreen);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);

  // Global Scroll Lock for Fullscreen Focus
  useEffect(() => {
    if (isFullscreen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => { document.body.style.overflow = 'unset'; };
  }, [isFullscreen]);

  // Smooth Transform Glide (Synchronous Reference updates for zero input-latency)
  const animateTransform = (targetX: number, targetY: number, targetScale: number) => {
    // Interrupt any active automated transitions
    if (glideAnimationRef.current !== null) {
      cancelAnimationFrame(glideAnimationRef.current);
      glideAnimationRef.current = null;
    }

    const startX = transformRef.current.x;
    const startY = transformRef.current.y;
    const startScale = transformRef.current.scale;
    const startTime = performance.now();
    const duration = 450; // ms

    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Cubic easeOut function
      const ease = 1 - Math.pow(1 - progress, 3);

      transformRef.current = {
        x: startX + (targetX - startX) * ease,
        y: startY + (targetY - startY) * ease,
        scale: startScale + (targetScale - startScale) * ease
      };

      setTransform(transformRef.current);

      if (progress < 1) {
        glideAnimationRef.current = requestAnimationFrame(step);
      } else {
        glideAnimationRef.current = null;
      }
    };
    glideAnimationRef.current = requestAnimationFrame(step);
  };

  // Helper to instantly interrupt active transitions on manual interaction
  const interruptGlideTransition = () => {
    if (glideAnimationRef.current !== null) {
      cancelAnimationFrame(glideAnimationRef.current);
      glideAnimationRef.current = null;
    }
  };

  // Double click to zoom in at mouse position
  const handleDoubleClick = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    
    const mouseX = e.clientX - rect.left - rect.width / 2;
    const mouseY = e.clientY - rect.top - rect.height / 2;
    
    const currentScale = transformRef.current.scale || 0.001; // Safely protect against scale === 0
    const targetScale = Math.min(currentScale * 2.2, 10);
    const newX = mouseX - (mouseX - transformRef.current.x) * (targetScale / currentScale);
    const newY = mouseY - (mouseY - transformRef.current.y) * (targetScale / currentScale);
    
    animateTransform(newX, newY, targetScale);
  };

  // Recenter Viewport
  const handleRecenter = () => {
    animateTransform(0, 0, 0.8);
  };

  // Zoom Increments
  const handleZoom = (factor: number) => {
    const targetScale = Math.min(Math.max(transformRef.current.scale * factor, 0.1), 10);
    animateTransform(transformRef.current.x, transformRef.current.y, targetScale);
  };

  // Center on Selected Node
  const handleFocusNode = (node: StarNode) => {
    const { x: nx, y: ny } = getProjectedCoords(node.x, node.y);
    animateTransform(-nx * 1.8, -ny * 1.8, 1.8);
  };

  // Native Fullscreen API Controller with graceful Webkit/Safari fallbacks
  const handleToggleFullscreen = async () => {
    const container = canvasRef.current?.parentElement;
    if (!container) return;

    const doc = document as Document & { webkitFullscreenElement?: Element; webkitExitFullscreen?: () => Promise<void>; msExitFullscreen?: () => Promise<void> };
    const el = container as HTMLElement & { webkitRequestFullscreen?: () => Promise<void>; msRequestFullscreen?: () => Promise<void> };

    try {
      if (!doc.fullscreenElement && !doc.webkitFullscreenElement) {
        if (el.requestFullscreen) {
          await el.requestFullscreen();
        } else if (el.webkitRequestFullscreen) {
          await el.webkitRequestFullscreen();
        } else if (el.msRequestFullscreen) {
          await el.msRequestFullscreen();
        }
      } else {
        if (doc.exitFullscreen) {
          await doc.exitFullscreen();
        } else if (doc.webkitExitFullscreen) {
          await doc.webkitExitFullscreen();
        } else if (doc.msExitFullscreen) {
          await doc.msExitFullscreen();
        }
      }
    } catch (err) {
      console.error("Native Fullscreen Error:", err);
      setIsFullscreen(!isFullscreen);
    }
  };

  // Mouse Handlers for Dragging and Clicking
  const handleMouseDown = (e: React.MouseEvent) => {
    interruptGlideTransition();
    setIsDragging(true);
    setLastMouse({ x: e.clientX, y: e.clientY });
    mouseDownPos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    setIsDragging(false);
    if (!mouseDownPos.current) return;
    
    // Direct click detection using squared distance to completely avoid Math.sqrt computation
    const dx = e.clientX - mouseDownPos.current.x;
    const dy = e.clientY - mouseDownPos.current.y;
    const distSq = dx * dx + dy * dy;
    
    if (distSq < 16) { // 4px max travel threshold
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      
      const currentScale = transformRef.current.scale || 0.001;
      
      const mouseX = (e.clientX - rect.left - rect.width / 2 - transformRef.current.x) / currentScale;
      const mouseY = (e.clientY - rect.top - rect.height / 2 - transformRef.current.y) / currentScale;
      
      let closest: StarNode | null = null;
      let minDistSq = (25 / currentScale) ** 2; // Squared hit sensitivity radius
      
      data.forEach(node => {
        const { x: nx, y: ny } = getProjectedCoords(node.x, node.y);
        const ndistSq = (mouseX - nx) ** 2 + (mouseY - ny) ** 2;
        if (ndistSq < minDistSq) {
          minDistSq = ndistSq;
          closest = node;
        }
      });
      
      if (closest) {
        setSelectedNode(closest);
        handleFocusNode(closest);
      } else {
        setSelectedNode(null);
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    if (isDragging) {
      interruptGlideTransition();
      const dx = e.clientX - lastMouse.x;
      const dy = e.clientY - lastMouse.y;
      
      transformRef.current = {
        ...transformRef.current,
        x: transformRef.current.x + dx,
        y: transformRef.current.y + dy
      };
      
      setTransform(transformRef.current);
      setLastMouse({ x: e.clientX, y: e.clientY });
      return;
    }

    const currentScale = transformRef.current.scale || 0.001;
    const mouseX = (e.clientX - rect.left - rect.width / 2 - transformRef.current.x) / currentScale;
    const mouseY = (e.clientY - rect.top - rect.height / 2 - transformRef.current.y) / currentScale;

    let closest: StarNode | null = null;
    let minDistSq = (25 / currentScale) ** 2;

    data.forEach(node => {
      const { x: nx, y: ny } = getProjectedCoords(node.x, node.y);
      const ndistSq = (mouseX - nx) ** 2 + (mouseY - ny) ** 2;
      if (ndistSq < minDistSq) {
        minDistSq = ndistSq;
        closest = node;
      }
    });
    setHovered(closest);
  };

  // Sync state values to references to run the canvas draw loop continuously without React teardowns
  const transformRef = useRef(transform);
  const hoveredRef = useRef(hovered);
  const selectedNodeRef = useRef(selectedNode);
  const showConnectionsRef = useRef(showConnections);
  const dataRef = useRef(data);
  const isDarkRef = useRef(isDark);

  useEffect(() => { transformRef.current = transform; }, [transform]);
  useEffect(() => { hoveredRef.current = hovered; }, [hovered]);
  useEffect(() => { selectedNodeRef.current = selectedNode; }, [selectedNode]);
  useEffect(() => { showConnectionsRef.current = showConnections; }, [showConnections]);
  useEffect(() => { dataRef.current = data; }, [data]);
  useEffect(() => { isDarkRef.current = isDark; }, [isDark]);

  // Heritage Design System Dynamic Theme colors (Synchronized from actual CSS Variables)
  const [themeColors, setThemeColors] = useState({
    foreground: '#FFFFFF',
    background: '#0A0A0A',
    border: 'rgba(255, 255, 255, 0.1)',
    secondary: '#A0A5AA',
    accent: '#B8422E',
  });

  useEffect(() => {
    if (!mounted || !canvasRef.current) return;
    const computed = getComputedStyle(canvasRef.current);
    const getVar = (name: string, fallback: string) => {
      return computed.getPropertyValue(name).trim() || fallback;
    };

    setThemeColors({
      foreground: getVar('--foreground', isDark ? '#F7F5F2' : '#1A1C1E'),
      background: getVar('--background', isDark ? '#0A0A0A' : '#F7F5F2'),
      border: getVar('--border', isDark ? 'rgba(247, 245, 242, 0.1)' : 'rgba(26, 28, 30, 0.1)'),
      secondary: getVar('--secondary', isDark ? '#A0A5AA' : '#6C7278'),
      accent: getVar('--color-tertiary', '#B8422E'),
    });
  }, [mounted, theme, isDark]);

  const themeColorsRef = useRef(themeColors);
  useEffect(() => { themeColorsRef.current = themeColors; }, [themeColors]);

  // 🏛️ Pre-render background stars to an offscreen canvas for zero-allocation, ultra-fast drawing
  useEffect(() => {
    if (!mounted) return;
    const offscreen = document.createElement('canvas');
    offscreen.width = 4000;
    offscreen.height = 4000;
    const oCtx = offscreen.getContext('2d');
    if (oCtx) {
      const maxOpacity = isDark ? 0.45 : 0.18;
      oCtx.fillStyle = themeColors.foreground || '#FFFFFF';
      backgroundStars.forEach(star => {
        oCtx.globalAlpha = star.opacityMult * maxOpacity + 0.05;
        oCtx.fillRect(star.x + 2000, star.y + 2000, star.size, star.size);
      });
      starsCanvasRef.current = offscreen;
    }
  }, [mounted, backgroundStars, themeColors, isDark]);

  // Canvas Backing-Store Resizing & High-DPI Scaling Controller
  useEffect(() => {
    if (!mounted || !canvasRef.current) return;
    const canvas = canvasRef.current;
    let resizeAnimationFrameId: number;
    let dprMedia: MediaQueryList | null = null;

    const updateSize = (width: number, height: number) => {
      const currentDpr = window.devicePixelRatio || 1;
      const newWidth = Math.floor(width * currentDpr);
      const newHeight = Math.floor(height * currentDpr);
      
      if (canvas.width !== newWidth || canvas.height !== newHeight) {
        canvas.width = newWidth;
        canvas.height = newHeight;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
      }
    };

    const parent = canvas.parentElement;
    if (parent) {
      const rect = parent.getBoundingClientRect();
      updateSize(rect.width, rect.height);
    }

    const resizeObserver = new ResizeObserver((entries) => {
      if (!entries || entries.length === 0) return;
      const entry = entries[0];
      const { width, height } = entry.contentRect;

      cancelAnimationFrame(resizeAnimationFrameId);
      resizeAnimationFrameId = requestAnimationFrame(() => {
        updateSize(width, height);
      });
    });

    if (parent) {
      resizeObserver.observe(parent);
    }

    const handleDPRChange = () => {
      const currentCanvas = canvasRef.current;
      if (currentCanvas && currentCanvas.parentElement) {
        const rect = currentCanvas.parentElement.getBoundingClientRect();
        cancelAnimationFrame(resizeAnimationFrameId);
        resizeAnimationFrameId = requestAnimationFrame(() => {
          updateSize(rect.width, rect.height);
        });
      }
      setupDPRObserver();
    };

    const setupDPRObserver = () => {
      if (dprMedia) {
        dprMedia.removeEventListener('change', handleDPRChange);
      }
      dprMedia = window.matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
      dprMedia.addEventListener('change', handleDPRChange);
    };

    setupDPRObserver();

    return () => {
      resizeObserver.disconnect();
      cancelAnimationFrame(resizeAnimationFrameId);
      if (dprMedia) {
        dprMedia.removeEventListener('change', handleDPRChange);
      }
    };
  }, [mounted]);

  // Non-passive wheel event listener to prevent browser pinch-to-zoom page scale shifts and scroll collisions
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      interruptGlideTransition();
      
      let deltaFactor = 0.0015;
      if (e.ctrlKey) {
        deltaFactor = 0.008;
      }
      const delta = -e.deltaY * deltaFactor;
      
      const nextScale = Math.min(Math.max(transformRef.current.scale + delta, 0.08), 10);
      transformRef.current = {
        ...transformRef.current,
        scale: nextScale
      };
      
      setTransform(transformRef.current);
    };

    const handleGesture = (e: Event) => {
      e.preventDefault();
    };

    container.addEventListener('wheel', handleWheel, { passive: false });
    container.addEventListener('gesturestart', handleGesture, { passive: false });
    container.addEventListener('gesturechange', handleGesture, { passive: false });

    return () => {
      container.removeEventListener('wheel', handleWheel);
      container.removeEventListener('gesturestart', handleGesture);
      container.removeEventListener('gesturechange', handleGesture);
    };
  }, [mounted]);

  // High-Performance Drawing Loop
  useEffect(() => {
    if (!mounted || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let time = 0;
    let lastTime = performance.now();

    const draw = () => {
      const currentTransform = transformRef.current;
      const currentHovered = hoveredRef.current;
      const currentSelectedNode = selectedNodeRef.current;
      const currentShowConnections = showConnectionsRef.current;
      const currentData = dataRef.current;
      const currentIsDark = isDarkRef.current;

      const now = performance.now();
      const deltaTime = Math.min((now - lastTime) / 1000, 0.1);
      lastTime = now;
      time += deltaTime * 0.36;

      const roomColors = currentIsDark ? ROOM_COLORS_DARK : ROOM_COLORS_LIGHT;
      const dpr = window.devicePixelRatio || 1;
      
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save();
      ctx.scale(dpr, dpr);
      
      ctx.fillStyle = 'transparent';
      ctx.strokeStyle = 'transparent';
      ctx.shadowBlur = 0;
      ctx.shadowColor = 'transparent';
      ctx.globalAlpha = 1.0;
      ctx.lineWidth = 1;
      ctx.setLineDash([]);
      
      const width = canvas.width / dpr;
      const height = canvas.height / dpr;

      // 1. Draw Background Stars with parallax motion
      if (starsCanvasRef.current) {
        ctx.save();
        ctx.translate(width / 2 + currentTransform.x * 0.15, height / 2 + currentTransform.y * 0.15);
        ctx.globalAlpha = currentIsDark ? 1.0 : 0.4;
        ctx.drawImage(starsCanvasRef.current, -2000, -2000);
        ctx.restore();
      }

      // Apply primary map transform and scale
      ctx.translate(width / 2 + currentTransform.x, height / 2 + currentTransform.y);
      ctx.scale(currentTransform.scale, currentTransform.scale);

      // 2. Draw Constellation Links
      if (currentShowConnections && currentData.length > 0) {
        for (let i = 0; i < currentData.length; i++) {
          const n1 = currentData[i];
          const { x: x1, y: y1 } = getProjectedCoords(n1.x, n1.y);
          
          let lineCount = 0;
          for (let j = i + 1; j < currentData.length; j++) {
            if (lineCount >= 3) break;
            
            const n2 = currentData[j];
            if (n1.room !== n2.room) continue;
            
            const { x: x2, y: y2 } = getProjectedCoords(n2.x, n2.y);
            const distSq = (x1 - x2) ** 2 + (y1 - y2) ** 2;
            
            if (distSq < 6400) {
              lineCount++;
              const isHoveredOrSelected = 
                currentHovered?.id === n1.id || currentHovered?.id === n2.id || 
                currentSelectedNode?.id === n1.id || currentSelectedNode?.id === n2.id;
              
              ctx.beginPath();
              ctx.moveTo(x1, y1);
              ctx.lineTo(x2, y2);
              
              const baseColor = roomColors[n1.room] || themeColorsRef.current.secondary;
              ctx.strokeStyle = baseColor;
              
              if (isHoveredOrSelected) {
                ctx.lineWidth = Math.max(1.0, 0.45 / currentTransform.scale);
                ctx.globalAlpha = currentIsDark ? 0.4 : 0.5;
              } else {
                ctx.lineWidth = Math.max(0.25, 0.12 / currentTransform.scale);
                ctx.globalAlpha = currentIsDark ? 0.08 : 0.12;
              }
              ctx.stroke();
            }
          }
        }
        ctx.globalAlpha = 1.0;
      }

      // 3. Draw Nodes (Neural Pulsars)
      currentData.forEach(node => {
        const { x, y } = getProjectedCoords(node.x, node.y);
        const isHovered = currentHovered?.id === node.id;
        const isSelected = currentSelectedNode?.id === node.id;
        
        const baseColor = roomColors[node.room] || themeColorsRef.current.secondary;
        const pulseOffset = pulseOffsetsRef.current[node.id] || 0;
        const pulseScale = (isHovered || isSelected) ? 1.5 : (1 + Math.sin(time + pulseOffset * 0.1) * 0.2);
        
        const baseRadius = (isHovered || isSelected) ? 6 : 2.5;
        const minPhysicalRadius = (isHovered || isSelected) ? 2.5 : 1.3;
        const radius = Math.max(baseRadius, minPhysicalRadius / currentTransform.scale);

        ctx.beginPath();
        ctx.arc(x, y, radius * pulseScale, 0, Math.PI * 2);
        ctx.fillStyle = baseColor;
        
        if (isHovered || isSelected) {
          ctx.shadowBlur = currentIsDark ? 25 : 15;
          ctx.globalAlpha = 1.0;
        } else {
          ctx.shadowBlur = currentIsDark ? 8 : 4;
          ctx.globalAlpha = currentIsDark ? 0.75 : 0.85;
        }
        ctx.shadowColor = baseColor;
        
        ctx.fill();
        ctx.shadowBlur = 0;
        ctx.globalAlpha = 1.0;

        if (isHovered && !isSelected) {
          ctx.strokeStyle = baseColor;
          ctx.lineWidth = Math.max(0.5, 0.22 / currentTransform.scale);
          ctx.beginPath();
          ctx.arc(x, y, Math.max(14 * pulseScale, 6.0 / currentTransform.scale), 0, Math.PI * 2);
          ctx.stroke();
        }
      });

      // 4. Draw Selected Active Target Reticle
      if (currentSelectedNode) {
        const { x: sx, y: sy } = getProjectedCoords(currentSelectedNode.x, currentSelectedNode.y);
        const baseColor = roomColors[currentSelectedNode.room] || themeColorsRef.current.secondary;
        
        ctx.save();
        ctx.strokeStyle = baseColor;
        ctx.lineWidth = Math.max(1.2, 0.5 / currentTransform.scale);
        ctx.setLineDash([3, 3]);
        
        ctx.beginPath();
        ctx.arc(sx, sy, Math.max(18 + Math.sin(time * 6) * 2, 8.0 / currentTransform.scale), time, time + Math.PI * 2);
        ctx.stroke();
        
        ctx.setLineDash([]);
        ctx.lineWidth = Math.max(0.5, 0.2 / currentTransform.scale);
        ctx.beginPath();
        
        const armLength = Math.max(26, 12.0 / currentTransform.scale);
        const innerGap = Math.max(12, 5.0 / currentTransform.scale);
        
        ctx.moveTo(sx - armLength, sy); ctx.lineTo(sx - innerGap, sy);
        ctx.moveTo(sx + innerGap, sy); ctx.lineTo(sx + armLength, sy);
        ctx.moveTo(sx, sy - armLength); ctx.lineTo(sx, sy - innerGap);
        ctx.moveTo(sx, sy + innerGap); ctx.lineTo(sx, sy + armLength);
        ctx.stroke();
        
        ctx.restore();
      }

      ctx.restore();
      animationFrameId = requestAnimationFrame(draw);
    };

    draw();
    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [mounted, backgroundStars]);

  const MapInner = (
    <div 
      ref={containerRef}
      className={`relative border border-[var(--border)] bg-[var(--background)] overflow-hidden group transition-[shadow,background-color,border-color] duration-300 artisan-shadow rounded-sm ${
        isFullscreen ? 'fixed inset-0 z-[9999] w-screen h-screen md:p-6 p-4 bg-[var(--background)]' : 'w-full h-[650px]'
      }`}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => setIsDragging(false)}
      onMouseMove={handleMouseMove}
      onDoubleClick={handleDoubleClick}
    >
      {/* Topology Header */}
      <div className="absolute top-8 left-10 z-[100] space-y-2 pointer-events-none select-none">
        <div className="flex items-center gap-3">
          <Compass className="w-4 h-4 text-[var(--accent)] animate-spin-slow" />
          <span className="font-heading text-[var(--foreground)] font-bold uppercase tracking-[0.3em] text-xs">Neural Network Topology</span>
        </div>
        <div className="text-[9px] font-mono opacity-40 uppercase tracking-widest">
          {isFullscreen ? "Full Spectrum Focus" : "Swarm Node Cluster View"} • {data.length} Signals
        </div>
      </div>

      {/* Floating Control Hub */}
      <ControlHub 
        showConnections={showConnections}
        setShowConnections={setShowConnections}
        handleZoom={handleZoom}
        handleRecenter={handleRecenter}
        handleToggleFullscreen={handleToggleFullscreen}
        isFullscreen={isFullscreen}
      />

      {/* Interactive Map Canvas */}
      <canvas 
        ref={canvasRef} 
        className={`w-full h-full cursor-grab active:cursor-grabbing transition-opacity duration-700 ${isDragging ? 'opacity-90' : 'opacity-100'}`} 
      />

      {/* Floating Inspector Panel (Selected Node Details) */}
      <AnimatePresence>
        {selectedNode && (
          <InspectorPanel 
            selectedNode={selectedNode}
            setSelectedNode={setSelectedNode}
            handleFocusNode={handleFocusNode}
            isFullscreen={isFullscreen}
            isDark={isDark}
          />
        )}
      </AnimatePresence>

      {/* Status Panel / Details for Hovered state (if no selected active node) */}
      <AnimatePresence>
        {hovered && !selectedNode && (
          <HoverPanel 
            hovered={hovered}
            isFullscreen={isFullscreen}
            isDark={isDark}
          />
        )}
      </AnimatePresence>

      {/* Coordinate Telemetry Indicator */}
      <div className="absolute bottom-8 left-10 z-[100] flex flex-col gap-1 pointer-events-none select-none">
        <div className="text-[7px] font-mono text-[var(--accent)] opacity-100 uppercase tracking-[0.2em] font-bold">Observer Telemetry</div>
        <div className="text-[9px] font-mono text-[var(--foreground)] opacity-40 italic">
          POS_X: {transform.x.toFixed(0)} • POS_Y: {transform.y.toFixed(0)} • ZOOM: {transform.scale.toFixed(2)}x
        </div>
      </div>

      {/* Color Coding Swarm Guide */}
      <SwarmLegend isDragging={isDragging} />
    </div>
  );

  if (!mounted) return <div className="w-full h-[650px] bg-black/5 border border-[var(--border)] rounded-sm" />;

  return MapInner;
}
