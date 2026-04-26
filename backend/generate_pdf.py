import json
import os
import subprocess
from pathlib import Path

def generate_pdf(json_path, output_dir, filename_prefix, gender="Auto"):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return None

    # Use source from JSON if available, otherwise fallback to filename_prefix
    source_name = data.get('source', f"{filename_prefix}_aligned.obj").replace('_', '\\_')

    tex_content = r"""\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{xcolor}
\usepackage{titlesec}
\usepackage{array}

\titleformat{\section}{\large\bfseries\color{blue!70!black}}{}{0em}{}[\titlerule]

\begin{document}

\begin{center}
    {\Huge \textbf{Tailor Measurement Sheet}} \\
    \vspace{2mm}
    {\large Source: SOURCE_NAME \quad | \quad Gender: GENDER_LABEL}
\end{center}

\section*{General Information}
\begin{tabular}{p{4cm} p{4cm}}
    \textbf{Metric} & \textbf{Value} \\
    \midrule
    Height & HEIGHT cm \\
    Scale Factor & SCALE_FACTOR \\
\end{tabular}

\section*{Upper Torso}
\begin{tabular}{p{4cm} p{4cm}}
    \textbf{Measurement} & \textbf{Value (cm)} \\
    \midrule
    Across Shoulder & ACROSS_SHOULDER \\
    Shoulder Width & SHOULDER_WIDTH \\
    Front Inner Shoulder & FRONT_INNER_SHOULDER \\
    Chest & CHEST \\
    Bust Size & BUST_SIZE \\
    Underbust & UNDERBUST \\
    Neck To Waist & NECK_TO_WAIST \\
\end{tabular}

\section*{Lower Torso}
\begin{tabular}{p{4cm} p{4cm}}
    \textbf{Measurement} & \textbf{Value (cm)} \\
    \midrule
    Waist & WAIST \\
    High Hip & HIGH_HIP \\
    Hip & HIP \\
\end{tabular}

\section*{Neck \& Arms}
\begin{tabular}{p{4cm} p{4cm} p{4cm} p{4cm}}
    \textbf{Neck Feature} & \textbf{Value (cm)} & \textbf{Arm Feature} & \textbf{Value (cm)} \\
    \midrule
    Neck Circumference & NECK_CIRC & Upper Arm Length & UPPER_ARM \\
    Neck Base & NECK_BASE & Lower Arm Length & LOWER_ARM \\
    Neck Length & NECK_LENGTH & Bicep Girth & BICEP \\
     &  & Forearm Girth & FOREARM \\
     &  & Elbow Width & ELBOW \\
\end{tabular}

\section*{Legs}
\begin{tabular}{p{4cm} p{4cm}}
    \textbf{Measurement} & \textbf{Value (cm)} \\
    \midrule
    Upper Leg Length & UPPER_LEG \\
    Lower Leg Length & LOWER_LEG \\
    Thigh Girth & THIGH \\
    Calf Girth & CALF \\
    Ankle Girth & ANKLE \\
    Knee Width & KNEE \\
\end{tabular}

\vfill
\begin{center}
    \textit{Generated for professional tailoring use.}
\end{center}

\end{document}
"""

    def get_val(path, default="N/A", precision=1):
        keys = path.split('.')
        val = data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        try:
            return f"{float(val):.{precision}f}"
        except:
            return str(val)

    # Replacements
    tex_content = tex_content.replace("SOURCE_NAME", source_name)
    tex_content = tex_content.replace("GENDER_LABEL", gender.capitalize())
    
    tex_content = tex_content.replace("HEIGHT", get_val("measurements.global.height"))
    tex_content = tex_content.replace("SCALE_FACTOR", get_val("scale", precision=4))
    
    tex_content = tex_content.replace("ACROSS_SHOULDER", get_val("measurements.upper_torso.across_shoulder"))
    tex_content = tex_content.replace("SHOULDER_WIDTH", get_val("measurements.upper_torso.shoulder_width"))
    tex_content = tex_content.replace("FRONT_INNER_SHOULDER", get_val("measurements.upper_torso.front_inner_shoulder"))
    tex_content = tex_content.replace("CHEST", get_val("measurements.upper_torso.chest"))
    tex_content = tex_content.replace("BUST_SIZE", get_val("measurements.upper_torso.bust_size"))
    tex_content = tex_content.replace("UNDERBUST", get_val("measurements.upper_torso.underbust"))
    tex_content = tex_content.replace("NECK_TO_WAIST", get_val("measurements.upper_torso.neck_to_waist"))
    
    tex_content = tex_content.replace("WAIST", get_val("measurements.lower_torso.waist"))
    tex_content = tex_content.replace("HIGH_HIP", get_val("measurements.lower_torso.high_hip"))
    tex_content = tex_content.replace("HIP", get_val("measurements.lower_torso.hip"))
    
    tex_content = tex_content.replace("NECK_CIRC", get_val("measurements.neck.neck_circumference"))
    tex_content = tex_content.replace("NECK_BASE", get_val("measurements.neck.neck_base"))
    tex_content = tex_content.replace("NECK_LENGTH", get_val("measurements.neck.neck_length"))
    
    tex_content = tex_content.replace("UPPER_ARM", get_val("measurements.arms.upper_arm_length"))
    tex_content = tex_content.replace("LOWER_ARM", get_val("measurements.arms.lower_arm_length"))
    tex_content = tex_content.replace("BICEP", get_val("measurements.arms.bicep_girth"))
    tex_content = tex_content.replace("FOREARM", get_val("measurements.arms.forearm_girth"))
    tex_content = tex_content.replace("ELBOW", get_val("measurements.arms.elbow_width"))
    
    tex_content = tex_content.replace("UPPER_LEG", get_val("measurements.legs.upper_leg_length"))
    tex_content = tex_content.replace("LOWER_LEG", get_val("measurements.legs.lower_leg_length"))
    tex_content = tex_content.replace("THIGH", get_val("measurements.legs.thigh_girth"))
    tex_content = tex_content.replace("CALF", get_val("measurements.legs.calf_girth"))
    tex_content = tex_content.replace("ANKLE", get_val("measurements.legs.ankle_girth"))
    tex_content = tex_content.replace("KNEE", get_val("measurements.legs.knee_width"))

    tex_path = Path(output_dir) / f"{filename_prefix}_measurements.tex"
    with open(tex_path, 'w') as f:
        f.write(tex_content)
        
    pdflatex_path = "/Library/TeX/texbin/pdflatex"
    if not os.path.exists(pdflatex_path):
        pdflatex_path = "pdflatex"
        
    try:
        # Run pdflatex twice for formatting (e.g., if we added longtable or refs)
        for _ in range(2):
            subprocess.run(
                [pdflatex_path, "-interaction=nonstopmode", "-output-directory", str(output_dir), str(tex_path)],
                check=True, capture_output=True
            )
    except subprocess.CalledProcessError as e:
        print("LaTeX compilation failed:")
        print(e.stdout.decode('utf-8', errors='ignore'))
        return None
        
    pdf_path = Path(output_dir) / f"{filename_prefix}_measurements.pdf"
    if pdf_path.exists():
        return str(pdf_path)
    return None
