'use client';

import { useEffect } from 'react';

export function AsciiBackground() {
	useEffect(() => {
		const embedScript = document.createElement('script');
		embedScript.type = 'text/javascript';
		embedScript.textContent = `
      !function(){
        if(!window.UnicornStudio){
          window.UnicornStudio={isInitialized:!1};
          var i=document.createElement("script");
          i.src="https://cdn.jsdelivr.net/gh/hiunicornstudio/unicornstudio.js@v1.4.33/dist/unicornStudio.umd.js";
          i.onload=function(){
            window.UnicornStudio.isInitialized||(UnicornStudio.init(),window.UnicornStudio.isInitialized=!0)
          };
          (document.head || document.body).appendChild(i)
        }
      }();
    `;
		document.head.appendChild(embedScript);

		// Add CSS to hide branding elements and crop canvas
		const style = document.createElement('style');
		style.textContent = `
      [data-us-project] {
        position: relative !important;
        overflow: hidden !important;
      }
      
      [data-us-project] canvas {
        clip-path: inset(0 0 10% 0) !important;
      }
      
      [data-us-project] * {
        pointer-events: none !important;
      }
      [data-us-project] a[href*="unicorn"],
      [data-us-project] button[title*="unicorn"],
      [data-us-project] div[title*="Made with"],
      [data-us-project] .unicorn-brand,
      [data-us-project] [class*="brand"],
      [data-us-project] [class*="credit"],
      [data-us-project] [class*="watermark"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        position: absolute !important;
        left: -9999px !important;
        top: -9999px !important;
      }
    `;
		document.head.appendChild(style);

		// Function to aggressively hide branding
		const hideBranding = () => {
			const projectDiv = document.querySelector('[data-us-project]');
			if (projectDiv) {
				// Find and remove any elements containing branding text
				const allElements = projectDiv.querySelectorAll('*');
				allElements.forEach((el) => {
					const text = (el.textContent || '').toLowerCase();
					if (text.includes('made with') || text.includes('unicorn')) {
						el.remove(); // Completely remove the element
					}
				});
			}
		};

		// Run immediately and periodically
		hideBranding();
		const interval = setInterval(hideBranding, 100);

		// Also try after delays
		setTimeout(hideBranding, 1000);
		setTimeout(hideBranding, 3000);
		setTimeout(hideBranding, 5000);

		return () => {
			clearInterval(interval);
			if (document.head.contains(embedScript)) {
				document.head.removeChild(embedScript);
			}
			if (document.head.contains(style)) {
				document.head.removeChild(style);
			}
		};
	}, []);

	return (
		<>
			{/* Vitruvian man animation centered and strictly bounded */}
			<div className="flex w-full items-center justify-center pointer-events-none mix-blend-screen opacity-100 brightness-[1.5] contrast-[1.2]">
				<div
					data-us-project="whwOGlfJ5Rz2rHaEUgHl"
					className="w-[320px] h-[320px] sm:w-[450px] sm:h-[450px] lg:w-[550px] lg:h-[550px]"
				/>
			</div>

			{/* Mobile stars background fallback just in case */}
			<div className="fixed inset-0 w-full h-full lg:hidden stars-bg opacity-30 pointer-events-none mix-blend-screen -z-10"></div>
			
			<style>{`
        .stars-bg {
          background-image: 
            radial-gradient(1px 1px at 20% 30%, white, transparent),
            radial-gradient(1px 1px at 60% 70%, white, transparent),
            radial-gradient(1px 1px at 50% 50%, white, transparent),
            radial-gradient(1px 1px at 80% 10%, white, transparent),
            radial-gradient(1px 1px at 90% 60%, white, transparent),
            radial-gradient(1px 1px at 33% 80%, white, transparent),
            radial-gradient(1px 1px at 15% 60%, white, transparent),
            radial-gradient(1px 1px at 70% 40%, white, transparent);
          background-size: 200% 200%, 180% 180%, 250% 250%, 220% 220%, 190% 190%, 240% 240%, 210% 210%, 230% 230%;
          background-position: 0% 0%, 40% 40%, 60% 60%, 20% 20%, 80% 80%, 30% 30%, 70% 70%, 50% 50%;
        }
      `}</style>
		</>
	);
}
