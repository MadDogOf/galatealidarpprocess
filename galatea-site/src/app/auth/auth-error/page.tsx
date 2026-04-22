'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowLeft } from 'lucide-react';

export default function AuthError() {
  return (
    <main className="relative min-h-screen bg-black text-white selection:bg-white/20 flex flex-col items-center justify-center font-mono p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full border border-red-500/30 bg-red-500/5 p-12 text-center"
      >
        <h1 className="text-2xl font-bold tracking-[0.2em] text-red-500 uppercase mb-4">[ ERR ] AUTH FAILURE</h1>
        <p className="text-white/60 mb-10 text-sm leading-relaxed">
          The biometric link between your identity and our system could not be verified. 
          Please ensure your Google account is operational and retry the sequence.
        </p>

        <Link 
          href="/" 
          className="inline-flex items-center gap-4 px-8 py-4 bg-white text-black font-bold text-sm uppercase hover:bg-[#ffd54f] transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          RETRY SEQUENCE
        </Link>
      </motion.div>

      {/* Accents */}
      <div className="fixed pointer-events-none top-0 left-0 w-16 h-16 border-t border-l border-white/10 m-8"></div>
      <div className="fixed pointer-events-none bottom-0 right-0 w-16 h-16 border-b border-r border-white/10 m-8"></div>
    </main>
  );
}
