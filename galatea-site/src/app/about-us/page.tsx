'use client';

import { motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

export default function AboutUs() {
  return (
    <main className="relative min-h-screen bg-black text-white selection:bg-white/20 overflow-hidden font-mono">
      {/* Background Glow */}
      <div
        aria-hidden="true"
        className={cn(
          'pointer-events-none absolute left-1/2 top-1/2 h-[60vh] w-[80vw] -translate-x-1/2 -translate-y-1/2 rounded-full',
          'bg-[radial-gradient(ellipse_at_center,rgba(255,200,0,0.03),transparent_70%)]',
          'blur-[60px]',
        )}
      />

      <nav className="fixed top-0 left-0 right-0 z-50 bg-black/40 backdrop-blur-md">
        <div className="container mx-auto px-4 lg:px-8 py-6">
          <Link 
            href="/" 
            className="group flex items-center gap-2 text-[10px] tracking-widest text-white/50 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-3 h-3 transition-transform group-hover:-translate-x-1" />
            BACK TO SYSTEM
          </Link>
        </div>
      </nav>

      <div className="container mx-auto px-4 lg:px-8 pt-32 pb-20 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="max-w-2xl"
        >
          <div className="flex items-center gap-4 mb-8">
            <div className="w-12 h-px bg-[#ffd54f]"></div>
            <h1 className="text-4xl font-bold tracking-tighter uppercase italic">About Galatea</h1>
          </div>
          
          <div className="space-y-8 text-white/70 leading-relaxed text-sm">
            <p>
              Galatea is a precision-tech fashion laboratory focused on the intersection of human biometrics and digital garment engineering.
            </p>
            <p>
              Our mission is to eliminate the friction between raw physical measurements and digital model generation, ensuring that every garment produced is a perfect match for the individual's unique physical signature.
            </p>
            <p className="text-[#ffd54f]/80">
              [ STATUS : OPERATIONAL ]
            </p>
          </div>
        </motion.div>
      </div>

      {/* Frame Accents */}
      <div className="fixed pointer-events-none bottom-0 left-0 w-16 h-16 border-b-2 border-l-2 border-white/10 m-8"></div>
      <div className="fixed pointer-events-none bottom-0 right-0 w-16 h-16 border-b-2 border-r-2 border-white/10 m-8"></div>
    </main>
  );
}
