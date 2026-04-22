'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';

const FRAMES = [
	{
		id: 'frame-1',
		video: 'VIDEO_01_IDLE_BEAR',
		headline: 'STEP 1: THE VISIT',
		subtext: 'You come to our Galatea store for precise scanning.',
	},
	{
		id: 'frame-2',
		video: 'VIDEO_02_LIDAR_SCAN',
		headline: 'STEP 2: LIDAR BIOMETRICS',
		subtext: 'We generate a precise, reusable digital model — your personal metahuman.',
	},
	{
		id: 'frame-3',
		video: 'VIDEO_03_RED_SHIRT_TIGHT',
		headline: 'STEP 3: VIRTUAL TRY-ON',
		subtext: 'See how garments from different brands fit your exact body.',
		microtext: "Too tight? We'll show you exactly where.",
	},
	{
		id: 'frame-4',
		video: 'VIDEO_04_RED_TENSION_MAP',
		headline: 'STEP 4: ISOLATE FAILURES',
		subtext: 'Our tension map highlights pressure zones and poor fit instantly.',
	},
	{
		id: 'frame-5',
		video: 'VIDEO_05_BLUE_SHIRT',
		headline: 'STEP 5: SECURE THE FIT',
		subtext: 'Switch styles, sizes, or brands to find what actually works.',
	},
	{
		id: 'frame-6',
		video: 'VIDEO_06_BLUE_TENSION_MAP',
		headline: 'STEP 6: VALIDATE RELIEFS',
		subtext: 'Compare tension maps and see the improvement in real time.',
	},
	{
		id: 'frame-7',
		video: 'VIDEO_07_IDLE_BEAR',
		headline: 'STEP 7: SHOP & TAILOR',
		subtext: 'Virtually try on your favorite brands before checkout, or send your 3D scan to a tailor for a flawless custom fit.',
	},
	{
		id: 'frame-8',
		video: 'VIDEO_07_FINAL',
		headline: 'STEP 8: THE INFINITE WARDROBE',
		subtext: 'Try infinite garments from the comfort of your home, natively fitted to your hyper-realistic digital model inside our virtual wardrobe.',
		microtext: 'Scan once. Buy right every time. Zero returns.',
	},
];

export function HowItWorksFlipbook() {
	const [active, setActive] = useState(0);
	const [hasStarted, setHasStarted] = useState(false);
	const [isMobile, setIsMobile] = useState(false);

	useEffect(() => {
		const checkMobile = () => setIsMobile(window.innerWidth < 768);
		checkMobile();
		window.addEventListener('resize', checkMobile);
		return () => window.removeEventListener('resize', checkMobile);
	}, []);

	const nextFrame = () => setActive((prev) => Math.min(prev + 1, FRAMES.length - 1));
	const prevFrame = () => setActive((prev) => Math.max(prev - 1, 0));
	const reset = () => {
		setActive(0);
		setHasStarted(false);
	};

	const frame = FRAMES[active];

	return (
		<div className="w-full max-w-5xl mx-auto flex flex-col items-center min-h-[600px]">
			<AnimatePresence mode="wait">
				{!hasStarted ? (
					<motion.div
						key="pre-start-state"
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0, transition: { duration: 0.5 } }}
						className="flex flex-col items-center w-full pb-16 pt-8"
					>
						<div className="mb-10 text-center">
							<h2 className="text-2xl font-bold tracking-widest text-white sm:text-3xl font-mono uppercase mb-4">How it works</h2>
							<p className="text-white/60 font-mono text-sm max-w-sm mx-auto">Flawless digital model generation.</p>
						</div>

						<button
							onClick={() => {
								setHasStarted(true);
								setActive(0);
							}}
							className="group relative flex items-center justify-center px-16 py-5 bg-white text-black overflow-hidden hover:bg-[#ffd54f] hover:scale-90 active:scale-90 transition-all duration-200 shadow-xl mb-4 rounded-lg"
						>
							<div className="w-0 h-0 border-t-[12px] border-t-transparent border-l-[20px] border-l-black border-b-[12px] border-b-transparent ml-1" />
						</button>

						{/* Shared LayoutID Video Container - Native Start */}
						<motion.div
							layoutId="video-container"
							transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
							className="relative w-full max-w-xs sm:max-w-sm lg:max-w-[340px] aspect-square overflow-hidden flex items-center justify-center group pointer-events-none"
						>
							<motion.div
								initial={{ opacity: 0 }}
								animate={{ opacity: 1 }}
								transition={{ duration: 1.5, ease: 'easeOut' }}
								className="absolute inset-0 flex items-center justify-center bg-[url('https://images.unsplash.com/photo-1634152962476-4b8a00e1915c?q=80&w=2000&auto=format&fit=crop')] bg-cover bg-center brightness-[0.2] contrast-[1.2] grayscale"
							/>
							<video
								src={`/videos/VIDEO_01_IDLE_BEAR${isMobile ? '_mobile' : ''}.mp4`}
								autoPlay
								loop
								muted
								playsInline
								preload="metadata"
								className="absolute inset-0 w-full h-full object-contain mix-blend-screen z-10"
							/>
						</motion.div>
					</motion.div>
				) : (
					<motion.div
						key="sequence-state"
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.8, delay: 0.3, ease: 'easeOut' }}
						className="relative w-full max-w-4xl overflow-hidden shadow-2xl backdrop-blur-sm p-4 sm:p-8 lg:p-12 mt-8 border-t border-white/5"
					>
						{/* Ambient Glow */}
						<div className="absolute top-0 left-1/2 -translate-x-1/2 w-[60%] h-[30%] bg-[#ffd54f]/5 blur-[120px] pointer-events-none" />

						<AnimatePresence mode="wait">
							<motion.div
								key={frame.id}
								initial={{ opacity: 0, scale: 0.98 }}
								animate={{ opacity: 1, scale: 1 }}
								exit={{ opacity: 0, scale: 1.02 }}
								transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
								className="w-full flex flex-col items-center"
							>
								{active !== FRAMES.length - 1 ? (
									<>
										{/* Shared LayoutID Video Container - Sequence Target */}
										<motion.div
											layoutId="video-container"
											transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
											className="relative w-full max-w-xs sm:max-w-sm lg:max-w-[340px] aspect-square overflow-hidden flex items-center justify-center group pointer-events-none mb-4 lg:mb-6"
										>
											<motion.div
												initial={{ scale: 1.05, opacity: 0.5 }}
												animate={{ scale: 1, opacity: 1 }}
												transition={{ duration: 1.5, ease: 'easeOut' }}
												className="absolute inset-0 flex items-center justify-center bg-[url('https://images.unsplash.com/photo-1634152962476-4b8a00e1915c?q=80&w=2000&auto=format&fit=crop')] bg-cover bg-center brightness-[0.2] contrast-[1.2] grayscale"
											/>
											
											{frame.video ? (
												<video
													src={`/videos/${frame.video}${isMobile ? '_mobile' : ''}.mp4`}
													autoPlay
													loop
													muted
													playsInline
													preload="metadata"
													className={cn("absolute inset-0 w-full h-full object-contain mix-blend-screen z-10 transition-transform duration-700", frame.video === 'VIDEO_02_LIDAR_SCAN' && "scale-[0.90]")}
													ref={(el) => { if (el) el.playbackRate = frame.video === 'VIDEO_07_IDLE_BEAR' ? 0.7 : 1; }}
												/>
											) : (
												<div className="absolute inset-0 flex items-center justify-center z-10">
													<div className="flex flex-col items-center gap-3 text-white/20 font-mono text-xs tracking-widest uppercase">
														<div className="w-6 h-6 border border-white/20 border-t-white/60 rounded-full animate-spin" />
														<span>[ VIDEO COMING SOON ]</span>
													</div>
												</div>
											)}
										</motion.div>

										{/* Narrative Action Bar */}
										<motion.div 
											initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.4 }}
											className="w-full flex flex-col sm:flex-row items-center sm:items-end justify-between border-t border-white/10 pt-8 gap-6 sm:gap-4"
										>
											<div className="flex-1 text-center sm:text-left">
												<h3 className="text-xl sm:text-2xl font-bold font-mono tracking-widest text-white uppercase mb-2">
													{frame.headline}
												</h3>
												<p className="text-sm sm:text-base font-mono text-white/60 leading-relaxed mb-2 max-w-lg mx-auto sm:mx-0">
													{frame.subtext}
												</p>
												{frame.microtext && (
													<p className="text-xs font-mono text-[#ffd54f] uppercase tracking-[0.2em] font-semibold mt-2">
														{frame.microtext}
													</p>
												)}
											</div>

											{/* Action Controls */}
											<div className="flex-shrink-0 flex flex-col items-center sm:items-end gap-3 w-full sm:w-auto mt-4 sm:mt-0">
												<div className="text-[#ffd54f]/50 font-mono text-xs tracking-widest mb-2">
													SEQ {String(active + 1).padStart(2, '0')} / {String(FRAMES.length).padStart(2, '0')}
												</div>
												<div className="flex items-center gap-3 w-full sm:w-auto justify-center sm:justify-end">
													{active > 0 && (
														<button
															onClick={prevFrame}
															className="group relative flex items-center justify-center px-6 py-3 border border-white/20 text-white hover:bg-white hover:text-black hover:scale-90 active:scale-90 font-mono text-sm tracking-widest font-bold uppercase overflow-hidden transition-all duration-200"
														>
															<span className="relative z-10 flex items-center font-bold text-xl uppercase tracking-widest leading-none">
																&lt;
															</span>
														</button>
													)}
													<button
														onClick={nextFrame}
														className="group relative flex items-center justify-center px-8 py-3 bg-white text-black font-mono text-sm tracking-widest font-bold uppercase overflow-hidden hover:bg-[#ffd54f] hover:scale-90 active:scale-90 transition-all duration-200 w-full sm:w-auto"
													>
														<span className="relative z-10 flex items-center font-bold text-xl uppercase tracking-widest leading-none">
															&gt;
														</span>
													</button>
												</div>
											</div>
										</motion.div>
									</>
								) : (
									<motion.div 
										initial={{ opacity: 0, scale: 0.95 }}
										animate={{ opacity: 1, scale: 1 }}
										transition={{ duration: 0.8, ease: "easeOut" }}
										className="w-full flex flex-col items-center justify-center text-center min-h-[400px] py-12"
									>
										<h3 className="text-4xl sm:text-5xl lg:text-6xl font-bold font-mono tracking-widest text-[#ffd54f] uppercase mb-8 leading-tight max-w-4xl mx-auto drop-shadow-lg">
											{frame.headline}
										</h3>
										<p className="text-lg sm:text-xl lg:text-2xl font-mono text-white/80 leading-relaxed mb-4 max-w-3xl mx-auto">
											{frame.subtext}
										</p>
										{frame.microtext && (
											<p className="text-sm sm:text-base font-mono text-white/40 uppercase tracking-[0.2em] font-medium mt-6 mb-16">
												{frame.microtext}
											</p>
										)}
										
										{/* Final Action Controls grouped cleanly */}
										<div className="flex flex-col items-center gap-4 border-t border-white/10 pt-10 w-full max-w-md">
											<div className="text-[#ffd54f]/50 font-mono text-xs tracking-widest mb-2">
												SEQ {String(active + 1).padStart(2, '0')} / {String(FRAMES.length).padStart(2, '0')}
											</div>
											<div className="flex items-center gap-4">
												<button
													onClick={prevFrame}
													className="group relative flex items-center justify-center px-6 py-3 border border-white/20 text-white hover:bg-white hover:text-black font-mono text-sm tracking-widest font-bold uppercase overflow-hidden transition-all duration-300"
												>
													<span className="relative z-10 flex items-center font-bold text-xl uppercase tracking-widest leading-none">
														&lt;
													</span>
												</button>
												<button
													onClick={reset}
													className="group relative flex items-center justify-center px-8 py-3 bg-white text-black font-mono text-sm tracking-widest font-bold uppercase hover:bg-[#ffd54f] transition-all duration-300"
												>
													<RotateCcw className="mr-3 w-4 h-4 transition-transform group-hover:-rotate-90" />
													Restart Sequence
												</button>
											</div>
										</div>
									</motion.div>
								)}
							</motion.div>
						</AnimatePresence>
					</motion.div>
				)}
			</AnimatePresence>
		</div>
	);
}
