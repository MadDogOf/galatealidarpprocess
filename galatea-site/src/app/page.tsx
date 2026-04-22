'use client';

import { useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { motion, useScroll, useTransform, useMotionValueEvent } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { HowItWorksFlipbook } from '@/components/ui/how-it-works-flipbook';
import { supabase } from '@/lib/supabase';

export default function Home() {
	const { scrollY } = useScroll();
	const [navVisible, setNavVisible] = useState(true);
	const lastScrollY = useRef(0);
	const { scrollYProgress } = useScroll();
	const [isMobile, setIsMobile] = useState(false);

	useEffect(() => {
		const checkMobile = () => setIsMobile(window.innerWidth < 768);
		checkMobile();
		window.addEventListener('resize', checkMobile);
		return () => window.removeEventListener('resize', checkMobile);
	}, []);

	useMotionValueEvent(scrollY, "change", (latest) => {
		if (latest > lastScrollY.current && latest > 150) {
			setNavVisible(false);
		} else {
			setNavVisible(true);
		}
		lastScrollY.current = latest;
	});

	const opacity = useTransform(scrollYProgress, [0, 0.2], [1, 0]);
	const scale = useTransform(scrollYProgress, [0, 0.2], [1, 0.95]);

	const [user, setUser] = useState<any>(null);
	const [name, setName] = useState('');
	const [email, setEmail] = useState('');
	const [emailError, setEmailError] = useState('');
	const [age, setAge] = useState('');
	const [source, setSource] = useState('');
	const [modelStyle, setModelStyle] = useState('');
	const [showModelStyles, setShowModelStyles] = useState(false);
	const [loading, setLoading] = useState(false);
	const [status, setStatus] = useState<{ type: 'success' | 'error' | 'info', message: string } | null>(null);

	useEffect(() => {
		const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
			setUser(session?.user ?? null);
			if (session?.user) {
				setEmail(session.user.email ?? '');
				setName(session.user.user_metadata.full_name ?? '');
			}
		});

		supabase.auth.getUser().then(({ data: { user } }) => {
			setUser(user);
			if (user) {
				setEmail(user.email ?? '');
				setName(user.user_metadata.full_name ?? '');
			}
		});

		return () => subscription.unsubscribe();
	}, []);

	// Queries State
	const [isQueriesOpen, setIsQueriesOpen] = useState(false);
	const [queryName, setQueryName] = useState('');
	const [queryEmail, setQueryEmail] = useState('');
	const [queryMessage, setQueryMessage] = useState('');
	const [queryLoading, setQueryLoading] = useState(false);
	const [queryStatus, setQueryStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);

	const handleGoogleSignIn = async () => {
		setLoading(true);
		try {
			const { error } = await supabase.auth.signInWithOAuth({
				provider: 'google',
				options: {
					redirectTo: `${window.location.origin}/api/auth/callback`
				}
			});
			if (error) throw error;
		} catch (err: any) {
			setStatus({ type: 'error', message: err.message || 'GOOGLE AUTH FAILURE.' });
			setLoading(false);
		}
	};

	const handleWaitlistJoin = async (e: React.FormEvent) => {
		e.preventDefault();

		if (!user) {
			handleGoogleSignIn();
			return;
		}

		setLoading(true);
		setStatus(null);

		try {
			const { error } = await supabase.rpc('upsert_waitlist', {
				p_email: email,
				p_name: name,
				p_age: parseInt(age),
				p_source: source
			});

			if (error) throw error;
			
			setStatus({ type: 'success', message: 'DATA TRANSMITTED. YOU ARE ON THE LIST.' });
		} catch (err: any) {
			setStatus({ type: 'error', message: err.message || 'SYSTEM FAILURE. PLEASE RETRY.' });
		} finally {
			setLoading(false);
		}
	};



	const handleQuerySubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setQueryLoading(true);
		setQueryStatus(null);

		try {
			const { error } = await supabase
				.from('queries')
				.insert([
					{ name: queryName, email: queryEmail, message: queryMessage }
				]);

			if (error) throw error;

			setQueryStatus({ type: 'success', message: 'QUERY RECEIVED. WE\'LL HELP YOU OUT SOON.' });
			setQueryName('');
			setQueryEmail('');
			setQueryMessage('');
			setTimeout(() => setIsQueriesOpen(false), 3000);
		} catch (err: any) {
			setQueryStatus({ type: 'error', message: 'SYSTEM FAILURE. PLEASE RETRY.' });
		} finally {
			setQueryLoading(false);
		}
	};

	return (
		<main className="relative min-h-screen selection:bg-white/20 bg-black overflow-x-hidden">
			{/* Shared Ambient Glow */}

			{/* Top Header / Frame */}
			<motion.div 
				initial={{ y: 0 }}
				animate={{ y: navVisible ? 0 : -100 }}
				transition={{ duration: 0.3, ease: "easeInOut" }}
				className="fixed top-0 left-0 right-0 z-50 bg-black/40 backdrop-blur-md"
			>
				<div className="container mx-auto px-4 lg:px-8 py-4 lg:py-6 flex items-center justify-between">
					<div className="flex items-center">
						<Link href="/" className="relative inline-block text-2xl font-black tracking-[0.2em] font-mono text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.3)] hover:scale-105 transition-transform">
							GALATEA
						</Link>
					</div>
					
					<div className="hidden lg:flex items-center gap-12 text-xs font-mono text-white/50 tracking-[0.3em] font-bold">
						<Link href="/about-us" className="hover:text-[#ffd54f] hover:drop-shadow-[0_0_8px_rgba(255,213,79,0.4)] hover:scale-90 transition-all duration-200 inline-block">ABOUT US</Link>
						<a href="#sustainability" className="hover:text-[#4ade80] hover:drop-shadow-[0_0_8px_rgba(74,222,128,0.4)] hover:scale-90 transition-all duration-200 inline-block">OUR GOALS</a>
						<a href="#what-we-do" className="hover:text-[#ffd54f] hover:drop-shadow-[0_0_8px_rgba(255,213,79,0.4)] hover:scale-90 transition-all duration-200 inline-block">WORKFLOW</a>
						<a href="#queries" className="hover:text-[#ffd54f] hover:drop-shadow-[0_0_8px_rgba(255,213,79,0.4)] hover:scale-90 transition-all duration-200 inline-block">QUERIES</a>
						<a href="#contact" className="hover:text-[#ffd54f] hover:drop-shadow-[0_0_8px_rgba(255,213,79,0.4)] hover:scale-90 px-4 py-2 border border-white/20 hover:border-[#ffd54f]/40 bg-white/5 transition-all duration-200 inline-block">SIGN UP</a>
					</div>
				</div>
			</motion.div>



			{/* Hero Section */}
			<motion.section
				style={{ opacity, scale }}
				className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-4 pt-20"
			>
				{/* Symmetrical glowing backdrop matching the Golden Theme */}
				<div
					aria-hidden="true"
					className={cn(
						'pointer-events-none absolute left-1/2 top-1/2 h-[60vh] w-[80vw] -translate-x-1/2 -translate-y-1/2 rounded-full',
						'bg-[radial-gradient(ellipse_at_center,rgba(255,200,0,0.03),transparent_70%)]',
						'blur-[60px]',
					)}
				/>
				
				{/* Looping Video Container inserted centrally above the hook */}
				<div className="relative w-full z-10 flex justify-center mt-0 -translate-y-8 pointer-events-auto">
					{/* Video Presentation */}
					<div className="w-[110px] sm:w-[150px] md:w-[190px] lg:w-[220px] flex justify-center items-center">
							<video
								src={isMobile ? "/videos/Black_ring_revolves_mobile.mp4" : "/videos/Black_ring_revolves_2026033114251.mp4"}
								autoPlay
								loop
								muted
								playsInline
								preload="metadata"
								className="w-full h-auto object-contain mix-blend-screen pointer-events-none"
							/>
					</div>
				</div>
				
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
					className="z-10 text-center relative w-full"
				>
					<div className="mt-4 flex justify-center">
						<div className="flex items-center gap-3 mb-4 opacity-80">
							<div className="w-8 sm:w-16 h-px bg-white/60"></div>
							<span className="text-white text-xs sm:text-sm font-mono tracking-widest font-bold uppercase">COMING TO COPENHAGEN</span>
							<div className="w-8 sm:w-16 h-px bg-white/60"></div>
						</div>
					</div>

					<p className="mx-auto mt-6 max-w-3xl text-2xl sm:text-3xl lg:text-4xl uppercase tracking-widest text-white font-mono font-bold leading-relaxed">
						Don't guess the fit. Try them on your exact 3D model first.
					</p>
				</motion.div>
			</motion.section>

			{/* What We Do Section */}
			<section id="what-we-do" className="relative z-10 mx-auto max-w-6xl px-4 py-32 sm:px-6 lg:px-8 border-t border-white/10 bg-black/80 backdrop-blur-md">
				{/* Interactive Flipbook Comic Strip */}
				<div className="w-full relative z-20">
					<HowItWorksFlipbook />
				</div>
			</section>

			{/* Our Goals Section */}
			<section id="sustainability" className="relative z-10 mx-auto max-w-6xl px-4 py-24 sm:px-6 lg:px-8 bg-black border-t border-white/5">
				<div className="mb-20 text-center lg:text-left">
					<h2 className="text-4xl font-bold tracking-[0.2em] text-white font-mono uppercase mb-4">
						Our Goals
					</h2>
					<p className="text-[#4ade80] font-mono text-sm tracking-widest font-bold">
						[ MISSION STATEMENT // SYSTEM.V1 ]
					</p>
				</div>
				
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-12 items-center">
					{/* Text Column */}
					<div className="flex flex-col space-y-16">
						<motion.div
							initial={{ opacity: 0, y: 20 }}
							whileInView={{ opacity: 1, y: 0 }}
							viewport={{ once: true }}
							transition={{ duration: 0.6 }}
						>
							<div className="flex items-center gap-4 mb-6">
								<div className="w-8 h-px bg-[#ffd54f]"></div>
								<h2 className="text-lg sm:text-xl font-bold tracking-widest text-[#ffd54f] uppercase font-mono">Eradicating the Remake Cycle</h2>
							</div>
							<p className="text-white/70 font-mono text-sm leading-relaxed text-justify sm:text-left">
								In Europe, road transport for last-mile deliveries and returns is a major driver of urban emissions, with returns effectively doubling the carbon footprint of a single purchase [European Environment Agency]. When a custom garment fails to fit, it triggers a disastrous reverse-logistics loop: delivery vans and trucks idling in city traffic to collect the return, shipping the item back, scrapping the fabric, and firing up a factory to remake it. Project Galatea is being built to eliminate this cycle. By guaranteeing the math is perfect on the first try, we cut the return trucks out of the equation entirely.
							</p>
						</motion.div>

						<motion.div
							initial={{ opacity: 0, y: 20 }}
							whileInView={{ opacity: 1, y: 0 }}
							viewport={{ once: true }}
							transition={{ duration: 0.6, delay: 0.2 }}
						>
							<div className="flex items-center gap-4 mb-6">
								<div className="w-8 h-px bg-[#ffd54f]"></div>
								<h2 className="text-lg sm:text-xl font-bold tracking-widest text-[#ffd54f] uppercase font-mono">Ending the Landfill Pipeline</h2>
							</div>
							<p className="text-white/70 font-mono text-sm leading-relaxed text-justify sm:text-left">
								The EU generates roughly 12.6 million tonnes of textile waste every year [European Environment Agency]. Even expensive, custom-made clothing finds its way to the trash if the fit is uncomfortable. Galatea's upcoming technology is designed to stop this waste at the source. By engineering garments based on your exact 3D biometric data, we are building a future where clothes actually fit, are worn for life, and never see a landfill.
							</p>
						</motion.div>
					</div>

					{/* Video Box Column */}
					<motion.div
						initial={{ opacity: 0, scale: 0.95 }}
						whileInView={{ opacity: 1, scale: 1 }}
						viewport={{ once: true }}
						transition={{ duration: 0.8 }}
						className="relative w-full max-w-xs mx-auto aspect-square overflow-hidden group shadow-2xl"
					>
						<video
							src={isMobile ? "/videos/Vehicle_drives_forward_mobile.mp4" : "/videos/Vehicle_drives_forward_202604021918.mp4"}
							autoPlay
							loop
							muted
							playsInline
							preload="none"
							className="absolute inset-0 w-full h-full object-cover"
							ref={(el) => {
						if (!el) return;
						el.playbackRate = 1.25;
						el.loop = false;
						const handler = () => {
							if (el.duration && el.currentTime >= el.duration - 0.1) {
								el.currentTime = 0;
								el.play();
							}
						};
						el.addEventListener('timeupdate', handler);
					}}
						/>
					</motion.div>
				</div>
			</section>

			{/* Contact / Waitlist Section */}
			<section id="contact" className="relative z-10 mx-auto max-w-4xl px-4 py-32 sm:px-6 lg:px-8 text-center bg-black/90">
				<div
					aria-hidden="true"
					className={cn(
						'pointer-events-none absolute left-1/2 top-1/2 h-[400px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full',
						'bg-[radial-gradient(ellipse_at_center,rgba(255,200,0,0.03),transparent_70%)]',
						'blur-[40px]',
					)}
				/>
				<motion.div
					initial={{ opacity: 0, scale: 0.95 }}
					whileInView={{ opacity: 1, scale: 1 }}
					viewport={{ once: true }}
					transition={{ duration: 0.6 }}
					className="relative overflow-hidden border border-[#ffd54f]/30 bg-black/40 px-6 py-20 sm:px-12 rounded-none"
				>
					<h2 className="text-2xl font-bold tracking-widest text-white mb-4 uppercase font-mono">Sign up for the waiting list</h2>
					<p className="text-[#ffd54f] mb-8 max-w-xl mx-auto font-mono text-sm leading-relaxed tracking-wider font-bold">
						100 FREE FULL BODY SCANS TO THE FIRST 100 SIGNUPS.
					</p>
					
					<div className="mx-auto flex flex-col max-w-4xl gap-4">
						{!user ? (
							<div className="flex flex-col items-center gap-8 py-10">
								<p className="text-white/60 font-mono text-sm max-w-sm">
									Authentication required to secure your slot.
								</p>
								<button
									onClick={handleGoogleSignIn}
									disabled={loading}
									className="group relative flex items-center gap-4 px-12 py-5 bg-white text-black font-mono text-sm font-bold uppercase hover:bg-[#ffd54f] hover:scale-95 active:scale-90 transition-all duration-300"
								>
									<svg className="w-5 h-5 transition-transform group-hover:scale-110" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
										<path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
										<path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
										<path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
										<path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
									</svg>
									{loading ? 'TRANSMITTING...' : 'Authenticate with Google'}
								</button>
							</div>
						) : (
							<form className="mx-auto flex flex-col w-full gap-4" onSubmit={handleWaitlistJoin}>
								<div className="flex flex-col gap-1 text-left">
									<label className="text-[10px] font-mono text-white/40 tracking-widest ml-1 uppercase">Authenticated as</label>
									<div className="w-full border border-[#ffd54f]/30 bg-[#ffd54f]/5 px-6 py-4 font-mono text-sm text-[#ffd54f] flex justify-between items-center group">
										<span>{email.toUpperCase()}</span>
										<button 
											type="button" 
											onClick={() => supabase.auth.signOut()}
											className="text-[9px] hover:underline opacity-50 group-hover:opacity-100 transition-opacity"
										>
											[ SIGN OUT ]
										</button>
									</div>
								</div>

								<input
									type="text"
									value={name}
									onChange={(e) => setName(e.target.value)}
									placeholder="FULL NAME"
									className="w-full rounded-none border border-white/20 bg-white/5 px-6 py-4 font-mono text-sm text-white placeholder:text-white/30 focus:border-[#ffd54f] focus:outline-none focus:ring-1 focus:ring-[#ffd54f]/50 transition-all uppercase mt-2"
									required
								/>
								
								<div className="flex gap-4 w-full">
									<input
										type="number"
										value={age}
										onChange={(e) => setAge(e.target.value)}
										placeholder="AGE"
										min="1"
										className="w-1/3 rounded-none border border-white/20 bg-white/5 px-6 py-4 font-mono text-sm text-white placeholder:text-white/30 focus:border-[#ffd54f] focus:outline-none focus:ring-1 focus:ring-[#ffd54f]/50 transition-all uppercase"
										required
									/>
									<select
										value={source}
										onChange={(e) => setSource(e.target.value)}
										className={cn("w-2/3 rounded-none border border-white/20 bg-white/5 px-6 py-4 font-mono text-sm focus:border-[#ffd54f] focus:outline-none focus:ring-1 focus:ring-[#ffd54f]/50 transition-all uppercase appearance-none", source ? "text-white" : "text-white/30")}
										required
									>
										<option value="" disabled className="bg-black text-white/30">HEARD FROM?</option>
										<option value="Friends" className="bg-black text-white">FRIENDS</option>
										<option value="Social Media Post" className="bg-black text-white">SOCIAL MEDIA</option>
										<option value="University Event" className="bg-black text-white">UNI EVENT</option>
										<option value="ChatGPT" className="bg-black text-white">CHATGPT</option>
										<option value="Internet" className="bg-black text-white">INTERNET</option>
										<option value="Other" className="bg-black text-white">OTHER</option>
									</select>
								</div>

								{/* Digital Model Style Preference */}
								<div className="border border-white/10 bg-white/[0.02] mt-2">
									<button
										type="button"
										onClick={() => setShowModelStyles(v => !v)}
										className="w-full flex items-center justify-between px-4 py-4 font-mono text-[10px] text-white/50 tracking-widest hover:text-white/80 transition-colors"
									>
										<span>DIGITAL MODEL PREFERENCE {modelStyle && <span className="text-[#ffd54f]">(SELECTED)</span>}</span>
										<span className={cn('transition-transform duration-200', showModelStyles ? 'rotate-90' : '')}>&gt;</span>
									</button>

									{showModelStyles && (
										<div className="px-4 pb-6">
											<p className="text-white/40 font-mono text-[10px] tracking-widest mb-6">
												All styles preserve your exact body proportions.
											</p>
											<div className="grid grid-cols-3 gap-6">
												{[
													{ id: 'hyper_realistic', label: 'Hyper Realistic', type: 'video', src: '/videos/VIDEO_01_IDLE_BEAR.mp4' },
													{ id: 'semi_anonymous', label: 'Semi Anonymous', type: 'video', src: '/videos/Polar_bear_idle_Animated.mp4' },
													{ id: 'anonymous', label: 'Anonymous', type: 'image', src: '/images/Polar_bear_idle.png' },
												].map(style => (
													<button
														type="button"
														key={style.id}
														onClick={() => setModelStyle(style.id)}
														className="flex flex-col gap-3 transition-all duration-200 opacity-100 hover:scale-95"
													>
														<div className={cn(
															'relative w-full aspect-square overflow-hidden bg-white/5 flex items-center justify-center',
															modelStyle === style.id ? 'ring-2 ring-[#ffd54f]' : 'ring-1 ring-white/10'
														)}>
															{style.type === 'video' ? (
																<video
																	src={isMobile ? style.src.replace('.mp4', '_mobile.mp4') : style.src}
																	autoPlay loop muted playsInline
																	preload="none"
																	className="absolute inset-0 w-full h-full object-cover"
																	ref={(el) => { if (el) el.playbackRate = style.id === 'semi_anonymous' ? 1.25 : 1; }}
																/>
															) : (
																<img
																	src={style.src}
																	alt={style.label}
																	className="absolute inset-0 w-full h-full object-cover"
																/>
															)}
														</div>
														<span className={cn(
															'font-mono text-[9px] tracking-wider text-center block',
															modelStyle === style.id ? 'text-[#ffd54f]' : 'text-white/60'
														)}>
															{style.label.toUpperCase()}
														</span>
													</button>
												))}
											</div>
										</div>
									)}
								</div>

								{status && (
									<div className={cn("text-xs font-mono p-4 border tracking-widest text-left mt-4", status.type === 'error' ? 'text-red-400 border-red-500/30 bg-red-500/5' : 'text-[#ffd54f] border-[#ffd54f]/30 bg-[#ffd54f]/5')}>
										[{status.type === 'error' ? 'ERR' : 'OK'}] {status.message}
									</div>
								)}

								<button
									type="submit"
									disabled={loading || !modelStyle}
									className="w-full mt-4 flex-none bg-white px-8 py-5 font-mono text-sm font-bold text-black hover:bg-[#ffd54f] hover:scale-[0.98] transition-all uppercase disabled:opacity-30 disabled:cursor-not-allowed"
								>
									{loading ? 'TRANSMITTING...' : 'Join the waitlist'}
								</button>
							</form>
						)}

						<p className="text-white/40 font-mono text-[10px] tracking-wider leading-relaxed text-center pt-6 max-w-lg mx-auto">
							Your scan data and body measurements are never shared with clothing brands, tailors, or third parties without your consent. Your data belongs to you.
						</p>
					</div>
				</motion.div>
			</section>

			{/* Queries Section */}
			<section id="queries" className="relative py-24 bg-black overflow-hidden border-t border-white/5">
				<div className="container mx-auto px-4 lg:px-8 text-center">
					<button 
						onClick={() => setIsQueriesOpen(!isQueriesOpen)}
						className="group flex flex-col items-center mx-auto px-12 sm:px-20 py-12 border border-white/10 bg-white/[0.02] hover:border-[#ffd54f]/50 hover:bg-white/5 hover:scale-95 active:scale-90 transition-all duration-300 mb-4"
					>
						<h2 className="text-2xl sm:text-4xl font-bold tracking-[0.2em] text-white font-mono uppercase mb-4 transition-all group-hover:text-[#ffd54f]">
							Send us your queries
						</h2>
						<p className="text-[#ffd54f]/60 font-mono text-[10px] sm:text-sm tracking-[0.3em] font-bold transition-all group-hover:text-[#ffd54f]">
							WE WOULD LOVE TO HELP YOU OUT.
						</p>
					</button>

					{isQueriesOpen && (
						<motion.div 
							initial={{ opacity: 0, y: 20 }}
							animate={{ opacity: 1, y: 0 }}
							className="max-w-2xl mx-auto bg-white/5 border border-white/10 p-8 sm:p-12 relative overflow-hidden"
						>
							{/* Form elements */}
							<form onSubmit={handleQuerySubmit} className="flex flex-col gap-6 text-left">
								<div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
									<input
										type="text"
										value={queryName}
										onChange={(e) => setQueryName(e.target.value)}
										placeholder="NAME"
										className="w-full rounded-none border border-white/20 bg-black/40 px-6 py-4 font-mono text-sm text-white placeholder:text-white/30 focus:border-[#ffd54f] focus:outline-none focus:ring-1 focus:ring-[#ffd54f]/50 transition-all uppercase"
										required
									/>
									<input
										type="email"
										value={queryEmail}
										onChange={(e) => setQueryEmail(e.target.value)}
										placeholder="EMAIL"
										className="w-full rounded-none border border-white/20 bg-black/40 px-6 py-4 font-mono text-sm text-white placeholder:text-white/30 focus:border-[#ffd54f] focus:outline-none focus:ring-1 focus:ring-[#ffd54f]/50 transition-all uppercase"
										required
									/>
								</div>
								<div className="relative">
									<textarea
										value={queryMessage}
										onChange={(e) => setQueryMessage(e.target.value.slice(0, 400))}
										placeholder="YOUR QUERY..."
										maxLength={400}
										rows={4}
										className="w-full rounded-none border border-white/20 bg-black/40 px-6 py-4 font-mono text-sm text-white placeholder:text-white/30 focus:border-[#ffd54f] focus:outline-none focus:ring-1 focus:ring-[#ffd54f]/50 transition-all uppercase resize-none"
										required
									/>
									<div className="absolute bottom-4 right-4 text-[10px] font-mono text-white/30 tracking-widest">
										{queryMessage.length} / 400
									</div>
								</div>

								{queryStatus && (
									<div className={cn(
										"text-xs font-mono p-4 border tracking-widest text-left",
										queryStatus.type === 'error' ? 'text-red-400 border-red-500/30 bg-red-500/5' : 'text-[#ffd54f] border-[#ffd54f]/30 bg-[#ffd54f]/5'
									)}>
										[{queryStatus.type === 'error' ? 'ERR' : 'OK'}] {queryStatus.message}
									</div>
								)}

								<button
									type="submit"
									disabled={queryLoading}
									className="w-full bg-white text-black font-mono text-sm font-bold py-4 hover:bg-[#ffd54f] transition-all uppercase disabled:opacity-50"
								>
									{queryLoading ? 'TRANSMITTING...' : 'SEND QUERY'}
								</button>
							</form>
						</motion.div>
					)}
				</div>
			</section>
			
			<footer className="relative z-20 border-t border-white/20 bg-black/80 backdrop-blur-sm">
				<div className="container mx-auto px-4 lg:px-8 py-3 flex items-center justify-between">
					<div className="flex items-center gap-3 lg:gap-6 text-[9px] font-mono text-white/50">
						<span className="hidden lg:inline">SYS.ACT // V1.0.0</span>
						<span className="lg:hidden">V1.0.0</span>
						<div className="hidden lg:flex gap-1">
							{[8, 14, 6, 12, 5, 15, 7, 10].map((h, i) => (
								<div key={i} className="w-1 bg-white/30" style={{ height: `${h}px` }}></div>
							))}
						</div>
						<span>© 2026 GALATEA</span>
					</div>
					
					<div className="flex items-center gap-2 text-[9px] font-mono text-white/30">
						<span>© 2026 GALATEA. ALL RIGHTS RESERVED.</span>
					</div>
				</div>
			</footer>

			<svg
				className="absolute -z-1 h-0 w-0"
				width="1440px"
				height="300px"
				viewBox="0 0 1440 300"
				xmlns="http://www.w3.org/2000/svg"
			>
				<defs>
					<filter
						id="glow-4"
						colorInterpolationFilters="sRGB"
						x="-50%"
						y="-200%"
						width="200%"
						height="500%"
					>
						<feGaussianBlur in="SourceGraphic" stdDeviation="4" result="blur4" />
						<feGaussianBlur in="SourceGraphic" stdDeviation="19" result="blur19" />
						<feGaussianBlur in="SourceGraphic" stdDeviation="9" result="blur9" />
						<feGaussianBlur in="SourceGraphic" stdDeviation="30" result="blur30" />
						
						{/* Multiplier matrices for GOLDEN GLOW (R=1, G=0.8, B=0) */}
						<feColorMatrix in="blur4" result="color-0-blur" type="matrix" values="1 0 0 0 0  0 0.8 0 0 0  0 0 0 0 0  0 0 0 0.8 0" />
						<feOffset in="color-0-blur" result="layer-0-offsetted" dx="0" dy="0" />
						
						<feColorMatrix in="blur19" result="color-1-blur" type="matrix" values="1 0 0 0 0  0 0.8 0 0 0  0 0 0 0 0  0 0 0 1 0" />
						<feOffset in="color-1-blur" result="layer-1-offsetted" dx="0" dy="2" />
						
						<feColorMatrix in="blur9" result="color-2-blur" type="matrix" values="1 0 0 0 0  0 0.8 0 0 0  0 0 0 0 0  0 0 0 0.65 0" />
						<feOffset in="color-2-blur" result="layer-2-offsetted" dx="0" dy="2" />
						
						<feColorMatrix in="blur30" result="color-3-blur" type="matrix" values="1 0 0 0 0  0 0.8 0 0 0  0 0 0 0 0  0 0 0 1 0" />
						<feOffset in="color-3-blur" result="layer-3-offsetted" dx="0" dy="2" />
						
						<feColorMatrix in="blur30" result="color-4-blur" type="matrix" values="0.7 0 0 0 0  0 0.5 0 0 0  0 0 0 0 0  0 0 0 1 0" />
						<feOffset in="color-4-blur" result="layer-4-offsetted" dx="0" dy="16" />
						
						<feColorMatrix in="blur30" result="color-5-blur" type="matrix" values="0.6 0 0 0 0  0 0.4 0 0 0  0 0 0 0 0  0 0 0 1 0" />
						<feOffset in="color-5-blur" result="layer-5-offsetted" dx="0" dy="64" />
						
						<feColorMatrix in="blur30" result="color-6-blur" type="matrix" values="0.3 0 0 0 0  0 0.2 0 0 0  0 0 0 0 0  0 0 0 1 0" />
						<feOffset in="color-6-blur" result="layer-6-offsetted" dx="0" dy="64" />
						
						<feColorMatrix in="blur30" result="color-7-blur" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.68 0" />
						<feOffset in="color-7-blur" result="layer-7-offsetted" dx="0" dy="64" />
						
						<feMerge>
							<feMergeNode in="layer-0-offsetted" />
							<feMergeNode in="layer-1-offsetted" />
							<feMergeNode in="layer-2-offsetted" />
							<feMergeNode in="layer-3-offsetted" />
							<feMergeNode in="layer-4-offsetted" />
							<feMergeNode in="layer-5-offsetted" />
							<feMergeNode in="layer-6-offsetted" />
							<feMergeNode in="layer-7-offsetted" />
							<feMergeNode in="layer-0-offsetted" />
							<feMergeNode in="SourceGraphic" />
						</feMerge>
					</filter>
				</defs>
			</svg>
		</main>
	);
}
