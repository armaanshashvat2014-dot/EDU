import streamlit as st
import os
import time
import re
import uuid
import json
import concurrent.futures
import base64
from pathlib import Path
from io import BytesIO
from PIL import Image

from google import genai
from google.genai import types
from google.cloud import firestore
from google.oauth2 import service_account

# ReportLab PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Image as RLImage, Table, TableStyle
)
from reportlab.lib.utils import ImageReader
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib import colors

# Matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

# -----------------------------
# 1) GLOBAL CONSTANTS & STYLING
# -----------------------------
st.set_page_config(page_title="helix.ai - Cambridge (CIE) Tutor", page_icon="📚", layout="centered")

# DYNAMIC BACKGROUND LOGIC FOR QUIZZES
quiz_bg_state = st.session_state.get("quiz_bg", "default")
if quiz_bg_state == "correct":
    bg_style = "radial-gradient(circle at 50% 50%, rgba(46, 204, 113, 0.25) 0%, #0a0a1a 80%)"
elif quiz_bg_state == "wrong":
    bg_style = "radial-gradient(circle at 50% 50%, rgba(231, 76, 60, 0.25) 0%, #0a0a1a 80%)"
else:
    bg_style = "radial-gradient(800px circle at 50% 0%, rgba(0, 212, 255, 0.12), rgba(0, 212, 255, 0.00) 60%), #0a0a1a"

# iOS 26 LIQUID GLASS CSS ENGINE
st.markdown(f"""
<style>
/* Core App Background & Typography */
.stApp {{
    background: {bg_style} !important;
    transition: background 0.6s ease-in-out;
    color: #f5f5f7 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}}

/* Sidebar Glassmorphism */
[data-testid="stSidebar"] {{
    background: rgba(25, 25, 35, 0.4) !important;
    backdrop-filter: blur(40px) !important;
    -webkit-backdrop-filter: blur(40px) !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}}

/* Native Streamlit Form & Container Glass UI */
[data-testid="stForm"],[data-testid="stVerticalBlockBorderWrapper"] {{
    background: rgba(255, 255, 255, 0.04) !important;
    backdrop-filter: blur(40px) !important;
    -webkit-backdrop-filter: blur(40px) !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 28px !important;
    padding: 10px !important;
    box-shadow: 0 16px 40px 0 rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2) !important;
    margin: 20px 0 !important;
}}

/* Glass Chat Bubbles */
[data-testid="stChatMessage"] {{
    background: rgba(255, 255, 255, 0.05) !important;
    backdrop-filter: blur(24px) !important;
    -webkit-backdrop-filter: blur(24px) !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 28px !important;
    padding: 20px !important;
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
    color: #fff !important;
    margin-bottom: 16px;
}}[data-testid="stChatMessage"] * {{ color: #f5f5f7 !important; }}

/* Glass Inputs (Chat & Forms) */
.stTextInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>textarea, .stNumberInput>div>div>input {{
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    border-radius: 12px !important;
    color: #fff !important;
}}
.stChatInputContainer {{ background: transparent !important; }}

/* Glossy Buttons */
.stButton>button {{
    background: linear-gradient(180deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.02) 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    border-radius: 20px !important;
    backdrop-filter: blur(20px) !important;
    color: #fff !important;
    font-weight: 600 !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}}

/* 🎯 FIX: Only apply hover effects on devices with a mouse to prevent Samsung mobile sticky hover bug! */
@media (hover: hover) and (pointer: fine) {{
    .stButton>button:hover {{
        background: linear-gradient(180deg, rgba(255,255,255,0.2) 0%, rgba(255,255,255,0.05) 100%) !important;
        border-color: rgba(255,255,255,0.4) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4) !important;
    }}
}}

.stButton>button:active {{
    transform: translateY(1px) !important;
    background: rgba(255,255,255,0.2) !important;
}}

/* Original Orange Thinking Animation */
.thinking-container {{ display: flex; align-items: center; gap: 8px; padding: 12px 16px; background-color: rgba(255,255,255,0.05); border-radius: 16px; margin: 10px 0; border-left: 3px solid #fc8404; backdrop-filter: blur(10px); }}
.thinking-text {{ color: #fc8404; font-size: 14px; font-weight: 600; }}
.thinking-dots {{ display: flex; gap: 4px; }}
.thinking-dot {{ width: 6px; height: 6px; border-radius: 50%; background-color: #fc8404; animation: thinking-pulse 1.4s infinite; }}
.thinking-dot:nth-child(2){{ animation-delay: 0.2s; }}
.thinking-dot:nth-child(3){{ animation-delay: 0.4s; }}
@keyframes thinking-pulse {{ 0%, 60%, 100% {{ opacity: 0.3; transform: scale(0.8); }} 30% {{ opacity: 1; transform: scale(1.2); }} }}

/* Typography */
.big-title {{ font-family: 'Inter', sans-serif; color: #00d4ff; text-align: center; font-size: 48px; font-weight: 1200; letter-spacing: -3px; margin-bottom: 0px; text-shadow: 0 0 12px rgba(0, 212, 255, 0.4); }}
.quiz-title {{ font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 20px; }}
.quiz-question-text {{ font-size: 28px; font-weight: 700; text-align: center; margin-bottom: 30px; line-height: 1.4; color: #fff; }}
.quiz-counter {{ color: #a0a0ab; font-size: 14px; font-weight: 600; margin-bottom: 15px; }}[data-testid="stFileUploaderDropzone"] {{ z-index: -1 !important; }}
</style>
""", unsafe_allow_html=True)

# MULTI-TENANT SCHOOL CODES SETUP
if "SCHOOL_CODES" in st.secrets:
    SCHOOL_CODES = dict(st.secrets["SCHOOL_CODES"])
else:
    SCHOOL_CODES = {}

# SYLLABUS TEXT
ENGLISH_SYLLABUS_G8_S9 = """
Chapter 1: Writing to explore and reflect (Travel writing, register, tone)
Chapter 2: Writing to inform and explain (Formal/informal, encyclopedia entries)
Chapter 3: Writing to argue and persuade (Persuasive techniques, essays)
Chapter 4: Descriptive writing (Atmosphere, structural devices)
Chapter 5: Narrative writing (Suspense, character, thrillers)
Chapter 6: Writing to analyse and compare (Implicit meaning, play elements)
Chapter 7: Testing your skills (Non-fiction & Fiction reading/writing)
"""

SYSTEM_INSTRUCTION = f"""
You are Helix, an elite Cambridge (CIE) Tutor and Examiner for Grade 6-8 students.

### RULE 1: RAG SEARCH & SCOPE (CRITICAL)
- Search the attached PDF textbooks using OCR FIRST.
- STRICT SCOPE: If the user requests specific chapters, topics, or a range (e.g., "Chapters 1-3" or "Fractions"), you MUST STRICTLY RESTRICT all questions to ONLY those requested chapters. NEVER generate questions from unrequested chapters.
- If (and ONLY if) the user asks for a general paper without specifying chapters, then your questions MUST be perfectly balanced across the entire uploaded syllabus. Do not overwork one chapter and ignore another.

### RULE 2: STRICT CAMBRIDGE QUESTION DEPTH & FORMATTING (CRITICAL)
You MUST design questions that are significantly harder than standard textbook drills. They must force multi-step reasoning, critical analysis, and data synthesis. Do NOT explicitly use the word "HOTS" or "Higher Order" in your output.

- INDIRECT QUESTIONS (NO TOPIC TITLES): NEVER give questions a title/heading that reveals the topic (e.g., DO NOT write "1. Fractions:", "2. Geometry:", or "3. Division:"). Just write "1.", "2.". The student MUST deduce which mathematical/scientific concept to apply based on the wording of the problem.
- NO CHILDISH TROPES: DO NOT use the "counting animal legs on a farm" trope. Use realistic, sophisticated scenarios.
- NO VAGUE SHAPES: For any transformation (rotation, reflection, enlargement), you MUST define the shape using exact grid coordinates (e.g., "A triangle has vertices at A(2,2), B(4,2), and C(2,5)").
- TABLE FORMATTING: You MUST use strict Markdown tables (e.g., `| Col1 | Col2 |`). DO NOT use spaces for alignment.

### RULE 3: GOOD VS. BAD EXAMPLES (STYLE GUIDE ONLY)
***CRITICAL INSTRUCTION: THE EXAMPLES BELOW ARE STRICTLY TO SHOW YOU THE REQUIRED DEPTH AND STRUCTURE. YOU ARE EXPRESSLY FORBIDDEN FROM COPYING THESE EXACT SCENARIOS. CREATE 100% UNIQUE QUESTIONS!***
**[MATH]** GOOD: "1. A theatre sells 26 child tickets and 15 adult tickets on Saturday. On Sunday... (a) Draw a dual frequency diagram...[3] (b) If child tickets made £143... [2]" 
**[SCIENCE]** GOOD: "1. Jamila adds 5 cm³ of hydrochloric acid to a sodium hydroxide solution... (a) Describe the type of reaction... [1] (b) Predict the pH...[2]" 
**[ENGLISH]** GOOD: "1. The writer states: 'its windows were dusty...'. Explain how this specific imagery helps the reader visualise...[2]"

### RULE 4: PAPER STRUCTURES
- MATH PAPERS: 30-45 main questions. Average ~2 bits (a, b). Combine concepts.
- SCIENCE PAPERS: 10-15 main questions. Average ~2 bits. MUST include a lab safety/equipment handling question, and anomalous data point identification.
- ENGLISH PAPERS: MUST HAVE EXACTLY 3 SECTIONS: 1. Reading Comprehension (15 bits). 2. Grammar (10 bits). 3. Writing (2 MANDATORY tasks).

### RULE 5: VISUAL SYNTAX (STRICT)
- YOU ARE CAPABLE OF GENERATING IMAGES. Use IMAGE_GEN:[Detailed description, white background] or PIE_CHART:[Label1:Value1, Label2:Value2]. 

### RULE 6: MARK SCHEME & TITLE
- TITLE FORMAT: MUST be formatted EXACTLY like this:
# Helix A.I.
## Practice Paper
###[SUBJECT] - [GRADE]
*(NEVER output the word "Stage" in the title, only use "Grade".)*
- MARK SCHEME: Put "## Mark Scheme" at the very bottom. You MUST use IMAGE_GEN:[...] inside the mark scheme to draw the correct visual answers for geometry/graph questions! State coordinates.

### RULE 7: Analytics for students (CRITICAL, HIDDEN):
At the VERY END of your response, output a hidden analytics block (unless a casual chat) wrapped EXACTLY like this:
===ANALYTICS_START===
{{ "subject": "Math", "grade": "Grade 7", "chapter_number": 4, "chapter_name": "Fractions", "score": 85, "weak_point": "None", "question_asked": "User query" }}
===ANALYTICS_END===
- `subject` MUST be "Math", "Biology", "Chemistry", "Physics", or "English".

### RULE 8: FLEXIBLE GRADING & CHAIN OF THOUGHT (CRITICAL)
When evaluating or grading a student's typed chat answer, you MUST act as a supportive human tutor:
1. SILENTLY solve the problem yourself to determine the undeniable correct answer based on the facts.
2. Compare your derived answer to the student's submitted answer, focusing ENTIRELY on SEMANTIC CORRECTNESS.
3. NEVER penalize a student if their answer is longer, more detailed, or phrased differently. If the expected answer is "No" and they write "No, because [reason]", mark it CORRECT.
4. Only mark an answer incorrect if the underlying logic is fundamentally wrong.
"""

QUIZ_SYSTEM_INSTRUCTION = f"""
You are an AI Quiz Engine. Your ONLY job is to output a single, raw JSON object based on the user's request. NEVER output conversational text, markdown formatting, or blockquotes like ```json. 

The JSON object MUST have this exact structure:
{{
    "question": "The text of the question?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_answer": "The exact text of the correct option",
    "explanation": "Brief explanation of why it is correct"
}}
"""

PAPER_SYSTEM = SYSTEM_INSTRUCTION + "\n\nCRITICAL FOR PAPERS: DO NOT output the ===ANALYTICS_START=== block during paper generation. Append[PDF_READY] at the end."

# -----------------------------
# 1.5) GRADE <-> STAGE MAPPING
# -----------------------------
GRADE_TO_STAGE = {"Grade 6": "Stage 7", "Grade 7": "Stage 8", "Grade 8": "Stage 9"}
STAGE_TO_GRADE = {v: k for k, v in GRADE_TO_STAGE.items()}
NUM_WORDS = {"six": "6", "seven": "7", "eight": "8", "nine": "9", "vi": "6", "vii": "7", "viii": "8", "ix": "9"}

def normalize_stage_text(s: str) -> str:
    s = (s or "").lower()
    for w, d in NUM_WORDS.items(): s = re.sub(rf"\b{w}\b", d, s)
    return s

def infer_stage_from_text(text: str):
    t = normalize_stage_text(text or "")
    if re.search(r"\b(grade|class|year)\W*6\b", t): return "Stage 7"
    if re.search(r"\b(grade|class|year)\W*7\b", t): return "Stage 8"
    if re.search(r"\b(grade|class|year)\W*8\b", t): return "Stage 9"
    if re.search(r"\bstage\W*7\b", t): return "Stage 7"
    if re.search(r"\bstage\W*8\b", t): return "Stage 8"
    if re.search(r"\bstage\W*9\b", t): return "Stage 9"
    return None

# -----------------------------
# 2) AUTH & FIRESTORE
# -----------------------------
if hasattr(st, "user"): auth_object = st.user
elif hasattr(st, "experimental_user"): auth_object = st.experimental_user
else: st.error("Streamlit version too old for Google Login."); st.stop()

is_authenticated = getattr(auth_object, "is_logged_in", False)

@st.cache_resource
def get_firestore_client():
    if "firebase" in st.secrets:
        creds = service_account.Credentials.from_service_account_info(dict(st.secrets["firebase"]))
        return firestore.Client(credentials=creds)
    return None

db = get_firestore_client()

def get_student_class_data(student_email):
    if not db: return None
    for c in db.collection("classes").where(filter=firestore.FieldFilter("students", "array_contains", student_email)).limit(1).stream():
        return {"id": c.id, **c.to_dict()}
    return None

def get_user_profile(email):
    if not db: return {"role": "student"}
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        profile = doc.to_dict()
        needs_update = False
        if not profile.get("display_name") and is_authenticated:
            profile["display_name"] = getattr(auth_object, "name", None) or email.split("@")[0]
            needs_update = True
        if profile.get("role") == "undefined":
            profile["role"] = "student"
            needs_update = True
        if needs_update: doc_ref.update(profile)
        return profile
    else:
        default_profile = {
            "role": "student", "teacher_id": None,
            "display_name": getattr(auth_object, "name", None) or email.split("@")[0] if is_authenticated else email.split("@")[0],
            "grade": "Grade 6", "school": None
        }
        doc_ref.set(default_profile)
        return default_profile

def create_global_class(class_id, teacher_email, grade, section, school_name):
    clean_id = class_id.strip().upper()
    if not clean_id or not db: return False, "Database error."
    class_ref = db.collection("classes").document(clean_id)

    @firestore.transactional
    def check_and_create(transaction, ref):
        snap = ref.get(transaction=transaction)
        if snap.exists: return False, f"Class '{clean_id}' already exists globally!"
        transaction.set(ref, {"created_by": teacher_email, "created_at": time.time(), "grade": grade, "section": section, "school": school_name, "students":[], "subjects":[]})
        return True, f"Class '{clean_id}' created successfully!"
    return check_and_create(db.transaction(), class_ref)

user_role = "guest"
user_profile = {} 
if is_authenticated:
    user_email = auth_object.email
    user_profile = get_user_profile(user_email)
    user_role = user_profile.get("role", "student")

# -----------------------------
# THREAD HELPERS
# -----------------------------
def get_threads_collection():
    return db.collection("users").document(auth_object.email).collection("threads") if is_authenticated and db else None

def get_all_threads():
    coll_ref = get_threads_collection()
    if coll_ref:
        try:
            return[{"id": doc.id, **doc.to_dict()} for doc in coll_ref.order_by("updated_at", direction=firestore.Query.DESCENDING).limit(15).stream()]
        except Exception: pass
    return[]

def get_default_greeting():
    return[{"role": "assistant", "content": "👋 **Hey there! I'm Helix!**\n\nI'm your friendly CIE tutor here to help you ace your CIE exams! 📖\n\nI can answer your doubts, draw diagrams, and create quizzes!\nYou can also **attach photos, PDFs, or text files directly in the chat box below!** 📸📄\n\nWhat are we learning today?", "is_greeting": True}]

def load_chat_history(thread_id):
    coll_ref = get_threads_collection()
    if coll_ref and thread_id:
        try:
            msgs_query = coll_ref.document(thread_id).collection("messages").order_by("idx").stream()
            msgs =[m.to_dict() for m in msgs_query]
            if msgs:
                return msgs
            doc = coll_ref.document(thread_id).get()
            if doc.exists and "messages" in doc.to_dict():
                return doc.to_dict().get("messages",[])
        except Exception: pass
    return get_default_greeting()

def compress_image_for_db(image_bytes: bytes) -> str:
    try:
        if not image_bytes: return None
        img = Image.open(BytesIO(image_bytes)).convert('RGB')
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception: return None

def save_chat_history():
    coll_ref = get_threads_collection()
    if not coll_ref: return
    safe_messages, detected_subjects, detected_grades =[], set(), set()

    for msg in st.session_state.messages:
        content_str = str(msg.get("content", ""))
        role = msg.get("role")
        if role == "user":
            q = content_str.lower()
            if any(k in q for k in["math", "algebra", "geometry", "calculate", "equation", "number", "fraction"]): detected_subjects.add("Math")
            if any(k in q for k in["science", "cell", "biology", "physics", "chemistry", "experiment", "gravity"]): detected_subjects.add("Science")
            if any(k in q for k in["english", "poem", "story", "essay", "writing", "grammar", "noun", "verb"]): detected_subjects.add("English")
            qn = normalize_stage_text(content_str)
            if re.search(r"\b(stage\W*7|grade\W*6|class\W*6|year\W*6)\b", qn): detected_grades.add("Grade 6")
            if re.search(r"\b(stage\W*8|grade\W*7|class\W*7|year\W*7)\b", qn): detected_grades.add("Grade 7")
            if re.search(r"\b(stage\W*9|grade\W*8|class\W*8|year\W*8)\b", qn): detected_grades.add("Grade 8")

        db_images =[]
        if msg.get("images"):
            db_images =[compress_image_for_db(img) for img in msg["images"] if img]
        elif msg.get("db_images"): db_images = msg["db_images"]

        user_attach_b64 = None
        user_attach_mime = msg.get("user_attachment_mime")
        user_attach_name = msg.get("user_attachment_name")
        if msg.get("user_attachment_bytes"):
            if "image" in (user_attach_mime or ""):
                user_attach_b64 = compress_image_for_db(msg["user_attachment_bytes"])
        elif msg.get("user_attachment_b64"):
            user_attach_b64 = msg["user_attachment_b64"]

        safe_msg = {
            "role": str(role), "content": content_str, "is_greeting": bool(msg.get("is_greeting", False)),
            "is_downloadable": bool(msg.get("is_downloadable", False)), "db_images":[i for i in db_images if i],
            "image_models": msg.get("image_models",[])
        }

        if user_attach_b64:
            safe_msg["user_attachment_b64"] = user_attach_b64
            safe_msg["user_attachment_mime"] = user_attach_mime
            safe_msg["user_attachment_name"] = user_attach_name
        elif user_attach_name:
            safe_msg["user_attachment_name"] = user_attach_name
            safe_msg["user_attachment_mime"] = user_attach_mime

        safe_messages.append(safe_msg)

    try: 
        thread_ref = coll_ref.document(st.session_state.current_thread_id)
        thread_ref.set({
            "updated_at": time.time(), 
            "metadata": {"subjects": list(detected_subjects), "grades": list(detected_grades)}
        }, merge=True)
        
        batch = db.batch()
        for idx, s_msg in enumerate(safe_messages):
            s_msg["idx"] = idx 
            msg_ref = thread_ref.collection("messages").document(str(idx).zfill(4))
            batch.set(msg_ref, s_msg)
        batch.commit()
        
    except Exception as e: 
        st.toast(f"⚠️ DB Error: {e}")

# -----------------------------
# GEMINI INIT & BULLETPROOF API ENGINE
# -----------------------------
api_key = os.environ.get("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
if not api_key: st.error("🚨 GOOGLE_API_KEY not found."); st.stop()
try: client = genai.Client(api_key=api_key)
except Exception as e: st.error(f"🚨 GenAI Error: {e}"); st.stop()

def generate_with_retry(model_target, contents, config, retries=3):
    for attempt in range(retries):
        try:
            return client.models.generate_content(model=model_target, contents=contents, config=config)
        except Exception as e:
            err_str = str(e).lower()
            if "503" in err_str or "unavailable" in err_str or "overloaded" in err_str or "429" in err_str or "quota" in err_str:
                if attempt < retries - 1:
                    time.sleep(1.5 ** attempt)
                    continue
            
            try:
                st.toast(f"⚠️ {model_target} overloaded. Switching to high-speed fallback...", icon="⚡")
                fallback_model = "gemini-2.5-flash-lite" if "flash" in model_target else "gemini-2.5-flash"
                return client.models.generate_content(model=fallback_model, contents=contents, config=config)
            except Exception as fallback_e:
                raise fallback_e
    return None

# -----------------------------
# GLOBAL VISUAL GENERATOR
# -----------------------------
def process_visual_wrapper(vp):
    error_logs =[]
    try:
        v_type, v_data = vp
        if v_type == "IMAGE_GEN":
            models_to_try =['gemini-3-pro-image-preview', 'gemini-3.1-flash-image-preview', 'imagen-4.0-fast-generate-001', 'gemini-2.5-flash-image']
            for model_name in models_to_try:
                try:
                    if "imagen" in model_name.lower():
                        result = client.models.generate_images(model=model_name, prompt=v_data, config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="4:3"))
                        if result.generated_images: return (result.generated_images[0].image.image_bytes, model_name, error_logs)
                    else:
                        result = client.models.generate_content(model=model_name, contents=[f"{v_data}\n\n(Important: Generate a 1k resolution image with a 4:3 aspect ratio.)"], config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
                        if result.candidates and result.candidates[0].content.parts:
                            for part in result.candidates[0].content.parts:
                                if getattr(part, "inline_data", None) and part.inline_data.data:
                                    return (part.inline_data.data, model_name, error_logs)
                except Exception as e: error_logs.append(f"**{model_name} Error:** {str(e)}")
            return (None, "All Models Failed", error_logs)

        elif v_type == "PIE_CHART":
            try:
                labels, sizes =[],[]
                for item in str(v_data).split(","):
                    if ":" in item:
                        k, v = item.split(":", 1)
                        labels.append(k.strip())
                        sizes.append(float(re.sub(r"[^\d\.]", "", v)))
                if not labels or not sizes or len(labels) != len(sizes): return (None, "matplotlib_failed", error_logs)
                fig = Figure(figsize=(5, 5), dpi=200); FigureCanvas(fig); ax = fig.add_subplot(111)
                ax.pie(sizes, labels=labels, autopct="%1.1f%%", startangle=140, colors=["#00d4ff", "#fc8404", "#2ecc71", "#9b59b6", "#f1c40f", "#e74c3c"][:len(labels)], textprops={"color": "black", "fontsize": 9}); ax.axis("equal")
                buf = BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
                return (buf.getvalue(), "matplotlib", error_logs)
            except Exception as e: return (None, "matplotlib_failed", error_logs)
    except Exception as e: return (None, "Crash",[str(e)])

# -----------------------------
# PDF HELPER
# -----------------------------
def md_inline_to_rl(text: str) -> str:
    s = (text or "").replace(r'\(', '').replace(r'\)', '').replace(r'\[', '').replace(r'\]', '').replace(r'\times', ' x ').replace(r'\div', ' ÷ ').replace(r'\circ', '°').replace(r'\pm', '±').replace(r'\leq', '≤').replace(r'\geq', '≥').replace(r'\neq', '≠').replace(r'\approx', '≈').replace(r'\pi', 'π').replace(r'\sqrt', '√').replace('\\', '')
    s = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'\1/\2', s)
    s = s.replace('$', '') 
    return re.sub(r"(?<!\*)\*(\S.+?)\*(?!\*)", r"<i>\1</i>", re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")))

def create_pdf(content: str, images=None, filename="Question_Paper.pdf"):
    buffer = BytesIO(); doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CustomTitle", parent=styles["Heading1"], fontSize=18, textColor=colors.HexColor("#00d4ff"), spaceAfter=12, alignment=TA_CENTER, fontName="Helvetica-Bold")
    body_style = ParagraphStyle("CustomBody", parent=styles["BodyText"], fontSize=11, spaceAfter=8, alignment=TA_LEFT, fontName="Helvetica")
    story, img_idx, table_rows =[], 0,[]

    def render_pending_table():
        nonlocal table_rows
        if not table_rows: return
        ncols = max(len(r) for r in table_rows)
        norm_rows = [[Paragraph(md_inline_to_rl(c), body_style) for c in list(r) + [""] * (ncols - len(r))] for r in table_rows]
        t = Table(norm_rows, colWidths=[doc.width / max(1, ncols)] * ncols)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00d4ff")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (0, 0), (-1, -1), "LEFT"), ("BOTTOMPADDING", (0, 0), (-1, 0), 8), ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9fa")), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
        story.extend([t, Spacer(1, 0.18*inch)]); table_rows =[]

    lines =[re.sub(r"\s*\(Source:.*?\)", "", l).strip() for l in str(content or "⚠️ No content").split("\n") if "[PDF_READY]" not in l.upper() and not l.strip().startswith(("Source(s):", "**Source(s):**"))]
    
    for s in lines:
        if s.startswith("|") and s.endswith("|") and s.count("|") >= 2:
            cells = [c.strip() for c in s.split("|")[1:-1]]
            if not all(re.fullmatch(r":?-+:?", c) for c in cells if c): table_rows.append(cells)
            continue
        render_pending_table()
        if not s: story.append(Spacer(1, 0.14*inch)); continue
        if s.startswith(("IMAGE_GEN:", "PIE_CHART:")):
            if images and img_idx < len(images) and images[img_idx]:
                try:
                    img_stream = BytesIO(images[img_idx]); rl_reader = ImageReader(img_stream)
                    iw, ih = rl_reader.getSize()
                    story.extend([Spacer(1, 0.12*inch), RLImage(img_stream, width=4.6*inch, height=4.6*inch*(ih/float(iw))), Spacer(1, 0.12*inch)])
                except Exception: pass
            img_idx += 1; continue
        if s.startswith("# "): story.append(Paragraph(md_inline_to_rl(s[2:].strip()), title_style))
        elif s.startswith("## "): story.append(Paragraph(md_inline_to_rl(s[3:].strip()), ParagraphStyle("CustomHeading", parent=styles["Heading2"], fontSize=14, spaceAfter=10, spaceBefore=10, fontName="Helvetica-Bold")))
        elif s.startswith("### "): story.append(Paragraph(f"<b>{md_inline_to_rl(s[4:].strip())}</b>", body_style))
        else: story.append(Paragraph(md_inline_to_rl(s), body_style))
    render_pending_table(); story.extend([Spacer(1, 0.28*inch), Paragraph("<i>Generated by helix.ai - Your CIE Tutor</i>", body_style)])
    doc.build(story); buffer.seek(0)
    return buffer

def safe_response_text(resp) -> str:
    try: return str(resp.text) if getattr(resp, "text", None) else "\n".join([p.text for c in (getattr(resp, "candidates", []) or[]) for p in (getattr(c.content, "parts", []) or[]) if getattr(p, "text", None)])
    except Exception: return ""

def generate_chat_title(client, messages):
    try:
        user_msgs =[m.get("content", "") for m in messages if m.get("role") == "user"]
        if not user_msgs: return "New Chat"
        response = generate_with_retry(
            model_target="gemini-2.5-flash", 
            contents=["Summarize this into a short chat title (max 4 words). Context: " + "\n".join(user_msgs[-3:])], 
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=50)
        )
        return safe_response_text(response).strip().replace('"', '').replace("'", "") or "New Chat"
    except Exception as e: st.toast(f"Title Gen Failed: {e}"); return "New Chat"

# -----------------------------
# 3) SESSION STATE & DIALOGS
# -----------------------------
if "current_thread_id" not in st.session_state: st.session_state.current_thread_id = str(uuid.uuid4())
if "messages" not in st.session_state: st.session_state.messages = get_default_greeting()
if "delete_requested_for" not in st.session_state: st.session_state.delete_requested_for = None

@st.dialog("⚠️ Maximum Chats")
def confirm_new_chat_dialog(oldest_thread_id):
    st.write("Limit of 15 chats reached. Delete oldest to create new?")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True): st.rerun()
    if c2.button("Yes", type="primary", use_container_width=True):
        try: 
            thread_ref = get_threads_collection().document(oldest_thread_id)
            for m in thread_ref.collection("messages").stream(): m.reference.delete()
            thread_ref.delete()
        except Exception: pass
        st.session_state.current_thread_id = str(uuid.uuid4()); st.session_state.messages = get_default_greeting(); st.rerun()

@st.dialog("🗑️ Delete Chat")
def confirm_delete_chat_dialog(thread_id_to_delete):
    st.write("Permanently delete this chat?")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True): st.session_state.delete_requested_for = None; st.rerun()
    if c2.button("Yes", type="primary", use_container_width=True):
        try:
            thread_ref = get_threads_collection().document(thread_id_to_delete)
            for m in thread_ref.collection("messages").stream(): m.reference.delete()
            thread_ref.delete()
        except Exception: pass
        if st.session_state.current_thread_id == thread_id_to_delete: 
            st.session_state.current_thread_id = str(uuid.uuid4()); st.session_state.messages = get_default_greeting()
        st.session_state.delete_requested_for = None; st.rerun()

@st.dialog("⚙️ Chat Settings")
def chat_settings_dialog(thread_data):
    st.caption(f"📚 **Subjects:** {', '.join(thread_data.get('metadata', {}).get('subjects',[])) or 'None'}")
    st.caption(f"🎓 **Grades:** {', '.join(thread_data.get('metadata', {}).get('grades',[])) or 'None'}")
    new_title = st.text_input("Rename Chat", value=thread_data.get("title", "New Chat"))
    if st.button("💾 Save", use_container_width=True):
        get_threads_collection().document(thread_data["id"]).set({"title": new_title, "user_edited_title": True}, merge=True); st.rerun()
    if st.button("🗑️ Delete", type="primary", use_container_width=True):
        st.session_state.delete_requested_for = thread_data['id']; st.rerun()

# -----------------------------
# 4) SIDEBAR
# -----------------------------
with st.sidebar:
    if is_authenticated and user_email.lower() in[e.lower() for e in st.secrets.get("ADMIN_EMAILS", [])] and st.button("⚙️ Admin Panel"):
        st.session_state.current_page = "admin"; st.rerun()

    if not is_authenticated:
        st.markdown("Chatting as a Guest!\nLog in with Google to save history!")
        if st.button("Log in with Google", type="primary", use_container_width=True): st.login(provider="google")
    else:
        st.success(f"Welcome back, {user_profile.get('display_name', 'User')}!")
        if st.button("Log out", use_container_width=True): st.logout()
        st.divider()
        
        st.markdown("<b style='color:#00d4ff'>🎯 ACTIVE GRADE</b>", unsafe_allow_html=True)
        prof_grade = user_profile.get("grade", "Grade 6")
        active_grade = st.selectbox("Set your grade context",["Grade 6", "Grade 7", "Grade 8"], index=["Grade 6", "Grade 7", "Grade 8"].index(prof_grade), label_visibility="collapsed")
        
        if active_grade != prof_grade:
            if db: db.collection("users").document(user_email).update({"grade": active_grade})
            user_profile["grade"] = active_grade
            st.rerun()
            
        st.session_state.active_grade = active_grade
        st.divider()

        if user_role == "student":
            st.markdown("<b style='color:#00d4ff'>📱 APP MODE</b>", unsafe_allow_html=True)
            st.session_state.app_mode = st.radio("Choose Mode", ["💬 AI Tutor", "⚡ Interactive Quiz"], label_visibility="collapsed")
            st.divider()

            if not user_profile.get("teacher_id"):
                with st.expander("🎓 Are you a Teacher?"):
                    if st.button("Verify Code") and (code_input := st.text_input("Teacher Code", type="password")) in SCHOOL_CODES:
                        db.collection("users").document(user_email).update({"role": "teacher", "school": SCHOOL_CODES[code_input]})
                        st.success("Verified!"); time.sleep(1); st.rerun()
            else:
                c = get_student_class_data(user_email)
                st.info(f"🏫 Class:\n**{c.get('id', 'Unknown') if c else 'Unknown'}**")

    if st.button("➕ New Chat", use_container_width=True):
        if is_authenticated and len(get_all_threads()) >= 15: confirm_new_chat_dialog(get_all_threads()[-1]["id"])
        else: st.session_state.current_thread_id = str(uuid.uuid4()); st.session_state.messages = get_default_greeting(); st.rerun()

    if is_authenticated:
        for t in get_all_threads():
            c1, c2 = st.columns([0.85, 0.15], vertical_alignment="center")
            if c1.button(f"{'🟢' if t['id'] == st.session_state.current_thread_id else '💬'} {t.get('title', 'New Chat')}", key=f"btn_{t['id']}", use_container_width=True):
                st.session_state.current_thread_id = t["id"]; st.session_state.messages = load_chat_history(t["id"]); st.rerun()
            if c2.button("⋮", key=f"set_{t['id']}", use_container_width=True): chat_settings_dialog(t)

if st.session_state.delete_requested_for: confirm_delete_chat_dialog(st.session_state.delete_requested_for)

def get_friendly_name(filename: str) -> str:
    name = (filename or "").replace(".pdf", "").replace(".PDF", "")
    parts = name.split("_")
    if len(parts) < 3 or parts[0] != "CIE": return name or "Textbook"
    stage_num = parts[1]
    grade_num = STAGE_TO_GRADE.get(f"Stage {stage_num}", "Unknown Grade")
    book_type = "Workbook" if "WB" in parts else "Textbook"
    if "ANSWERS" in parts: book_type += " Answers"
    subject = "Science" if "Sci" in parts else "Math" if "Math" in parts else "English" if "Eng" in parts else "Subject"
    part_str = " (Part 1)" if "1" in parts[2:] else " (Part 2)" if "2" in parts[2:] else ""
    return f"Cambridge {subject} {book_type} - Stage {stage_num} ({grade_num}){part_str}".strip()

def guess_mime(filename: str, fallback: str = "application/octet-stream") -> str:
    n = (filename or "").lower()
    return "image/jpeg" if n.endswith((".jpg", ".jpeg")) else "image/png" if n.endswith(".png") else "application/pdf" if n.endswith(".pdf") else fallback

def is_image_mime(m: str) -> bool: return (m or "").lower().startswith("image/")

@st.cache_resource(show_spinner=False)
def upload_textbooks():
    active_files = {"sci":[], "math": [], "eng":[]}
    pdf_map = {p.name.lower(): p for p in Path.cwd().rglob("*.pdf") if "cie" in p.name.lower()}
    target_files = list(pdf_map.keys())
    
    try: 
        existing = {f.display_name.lower(): f for f in client.files.list() if f.display_name}
    except Exception: 
        existing = {}
    
    with st.chat_message("assistant"): st.markdown(f"""<div class="thinking-container"><span class="thinking-text">📚 Synchronizing {len(target_files)} Textbooks...</span><div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div></div>""", unsafe_allow_html=True)
    
    def process_single_book(t):
        if t in existing and existing[t].state.name == "ACTIVE": return t, existing[t]
        if t in pdf_map:
            try:
                up = client.files.upload(file=str(pdf_map[t]), config={"mime_type": "application/pdf", "display_name": pdf_map[t].name})
                timeout = time.time() + 90
                while up.state.name == "PROCESSING" and time.time() < timeout:
                    time.sleep(3)
                    up = client.files.get(name=up.name)
                if up.state.name == "ACTIVE": return t, up
            except Exception as e: print(f"Upload Error {t}: {e}")
        return t, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_single_book, target_files))

    for t, file_obj in results:
        if file_obj:
            if "sci" in t: active_files["sci"].append(file_obj)
            elif "math" in t: active_files["math"].append(file_obj)
            elif "eng" in t: active_files["eng"].append(file_obj)
    return active_files

if is_authenticated and "textbook_handles" not in st.session_state:
    with st.spinner("Preparing curriculum..."): st.session_state.textbook_handles = upload_textbooks()

def select_relevant_books(query, file_dict, user_grade="Grade 6"):
    qn = normalize_stage_text(query)
    s7 = any(k in qn for k in ["stage 7", "grade 6", "year 7"])
    s8 = any(k in qn for k in["stage 8", "grade 7", "year 8"])
    s9 = any(k in qn for k in["stage 9", "grade 8", "year 9"])
    
    im = any(k in qn for k in["math", "algebra", "number", "fraction", "geometry", "calculate", "equation"])
    isc = any(k in qn for k in["sci", "biology", "physics", "chemistry", "experiment", "cell", "gravity"])
    ien = any(k in qn for k in["eng", "poem", "story", "essay", "writing", "grammar"])
    
    if not (s7 or s8 or s9):
        if user_grade == "Grade 6": s7 = True
        elif user_grade == "Grade 7": s8 = True
        elif user_grade == "Grade 8": s9 = True
        else: s8 = True
        
    if not (im or isc or ien): im = isc = ien = True
    sel =[]
    def add(k, act):
        if act: 
            for b in file_dict.get(k,[]):
                n = b.display_name.lower()
                if "answers" in n and user_role != "teacher": continue
                if (s7 and "cie_7" in n) or (s8 and "cie_8" in n) or (s9 and "cie_9" in n): 
                    sel.append(b)
                    break 
    
    add("math", im); add("sci", isc); add("eng", ien)
    return sel[:2]

# ==========================================
# APP ROUTING LOGIC
# ==========================================
render_chat_interface = False 

# --- TEACHER DASHBOARD ---
if user_role == "teacher":
    st.markdown("<div class='big-title' style='color:#fc8404;'>👨‍🏫 helix.ai / Teacher</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    user_school = user_profile.get("school")
    roster =[u for u in db.collection("users").where(filter=firestore.FieldFilter("school", "==", user_school)).stream() if u.to_dict().get("role") == "student"] if user_school else list(db.collection("users").where(filter=firestore.FieldFilter("teacher_id", "==", user_email)).stream())

    teacher_menu = st.radio("Menu",["Class Management", "Student Analytics", "Assign Papers", "AI Chat"], horizontal=True, label_visibility="collapsed")
    st.divider()

    if teacher_menu == "Class Management":
        st.subheader("🏫 Class Management")
        with st.form("create_class_form", clear_on_submit=True):
            cc1, cc2, cc3 = st.columns([0.4, 0.3, 0.3])
            grade_choice = cc1.selectbox("Grade", ["Grade 6", "Grade 7", "Grade 8"])
            section_choice = cc2.selectbox("Section", ["A", "B", "C", "D"])
            if cc3.form_submit_button("Create", use_container_width=True):
                success, msg = create_global_class(f"{grade_choice.split()[-1]}{section_choice}".upper(), user_email, grade_choice, section_choice, user_school)
                if success: st.success(msg); time.sleep(1); st.rerun()
                else: st.error(msg)
        
        my_classes = list(db.collection("classes").where(filter=firestore.FieldFilter("created_by", "==", user_email)).stream())
        if my_classes:
            with st.form("add_student_form", clear_on_submit=True):
                sc = st.selectbox("Class", [c.id for c in my_classes])
                em = st.text_input("Student Email")
                if st.form_submit_button("Add") and em:
                    db.collection("users").document(em.strip().lower()).set({"role": "student", "teacher_id": user_email, "school": user_school}, merge=True)
                    db.collection("classes").document(sc).update({"students": firestore.ArrayUnion([em.strip().lower()])})
                    st.success("Added!"); time.sleep(1); st.rerun()

    elif teacher_menu == "Assign Papers":
        st.subheader("📝 Assignment Creator")
        c1, c2 = st.columns(2)
        assign_title = c1.text_input("Title", "Chapter Quiz")
        assign_subject = c1.selectbox("Subject",["Math", "Biology", "Chemistry", "Physics", "English"])
        assign_grade = c1.selectbox("Grade",["Grade 6", "Grade 7", "Grade 8"])
        assign_difficulty = c2.selectbox("Difficulty",["Easy", "Medium", "Hard"])
        assign_marks = c2.number_input("Marks", 10, 100, 30, 5)
        assign_extra = st.text_area("Extra Instructions")

        if st.button("🤖 Generate with Helix AI", type="primary", use_container_width=True):
            with st.spinner("Writing paper..."):
                books = select_relevant_books(f"{assign_subject} {assign_grade}", st.session_state.textbook_handles, assign_grade)
                parts = []
                for b in books: parts.extend([types.Part.from_text(text=f"[Source: {b.display_name}]"), types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf")])
                
                parts.append(types.Part.from_text(text=f"Task: Generate a CIE {assign_subject} paper for {assign_grade} students.\nDifficulty: {assign_difficulty}. Marks: {assign_marks}.\nExtra Instructions: {assign_extra}"))
                
                try:
                    resp = generate_with_retry(
                        model_target="gemini-2.5-pro", 
                        contents=parts, 
                        config=types.GenerateContentConfig(system_instruction=PAPER_SYSTEM, temperature=0.1)
                    )
                    gen_paper = safe_response_text(resp)
                    
                    draft_imgs, draft_mods = [],[]
                    if v_prompts := re.findall(r"(IMAGE_GEN|PIE_CHART):\s*\[(.*?)\]", gen_paper):
                        with concurrent.futures.ThreadPoolExecutor(5) as exe:
                            for r in exe.map(process_visual_wrapper, v_prompts):
                                draft_imgs.append(r[0]); draft_mods.append(r[1])
                                if not r[0] and len(r)>2: st.error(f"Image Error: {r[2]}")

                    st.session_state.update(draft_paper=gen_paper, draft_images=draft_imgs, draft_models=draft_mods, draft_title=assign_title); st.rerun()
                except Exception as e: st.error(e)

        if st.session_state.get("draft_paper"):
            with st.expander("Preview", expanded=True):
                st.markdown(st.session_state.draft_paper.replace("[PDF_READY]", ""))
                if st.session_state.draft_images:
                    for i, m in zip(st.session_state.draft_images, st.session_state.draft_models):
                        if i: st.image(i, caption=m)
                try: st.download_button("Download PDF", data=create_pdf(st.session_state.draft_paper, st.session_state.draft_images), file_name=f"{st.session_state.draft_title}.pdf", mime="application/pdf")
                except Exception as e: st.error(f"PDF Gen Error: {e}")

    elif teacher_menu == "AI Chat": 
        render_chat_interface = True 

# --- STUDENT DASHBOARD ---
else:
    app_mode = st.session_state.get("app_mode", "💬 AI Tutor")
    
    # ⚡ ISOLATED JSON QUIZ MODE ⚡
    if app_mode == "⚡ Interactive Quiz":
        render_chat_interface = False
        
        # A) QUIZ SETUP
        if not st.session_state.get("quiz_active", False):
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.markdown("<div class='quiz-title'>⚙️ Configure Your Quiz</div>", unsafe_allow_html=True)
            with st.form("quick_quiz_form", border=False):
                with st.container(border=True):
                    c1, c2, c3 = st.columns(3)
                    q_subj = c1.selectbox("Subject",["Math", "Science", "English"])
                    current_active_grade = st.session_state.get("active_grade", user_profile.get("grade", "Grade 6"))
                    q_grade = c2.selectbox("Grade", ["Grade 6", "Grade 7", "Grade 8"], index=["Grade 6", "Grade 7", "Grade 8"].index(current_active_grade))
                    q_diff = c3.selectbox("Difficulty",["Easy", "Medium", "Hard"])
                    c4, c5 = st.columns([3, 1])
                    q_chap = c4.text_input("Chapter / Topic", placeholder="e.g., Chapter 4, Fractions, Forces...")
                    q_num = c5.selectbox("Questions",[5, 10, 15, 20])
                    
                    if st.form_submit_button("🚀 Start Interactive Quiz", type="primary", use_container_width=True):
                        st.session_state.quiz_params = {"subj": q_subj, "grade": q_grade, "diff": q_diff, "chap": q_chap, "num": q_num}
                        st.session_state.quiz_score = 0
                        st.session_state.quiz_current_q = 1
                        st.session_state.quiz_active = True
                        st.session_state.quiz_bg = "default"
                        st.rerun()
        
        # B) ACTIVE QUIZ SCREEN
        else:
            # Generate JSON Question via API
            if "quiz_current_q_data" not in st.session_state:
                with st.spinner("Generating next question..."):
                    p = st.session_state.quiz_params
                    prompt = f"Create a {p['diff']} multiple-choice question for a {p['grade']} {p['subj']} student. Topic: {p['chap']}. Provide 4 options."
                    books = select_relevant_books(f"{p['subj']} {p['grade']}", st.session_state.textbook_handles, p['grade'])
                    
                    parts = []
                    for b in books: parts.extend([types.Part.from_text(text=f"[Source: {b.display_name}]"), types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf")])
                    parts.append(prompt)

                    response = generate_with_retry("gemini-2.5-pro", parts, types.GenerateContentConfig(system_instruction=QUIZ_SYSTEM_INSTRUCTION, temperature=0.3))
                    try:
                        json_str = re.search(r'\{.*\}', safe_response_text(response), re.DOTALL).group(0)
                        st.session_state.quiz_current_q_data = json.loads(json_str)
                        st.session_state.quiz_user_answer = None 
                        st.session_state.quiz_bg = "default"
                        st.rerun()
                    except Exception as e:
                        st.error("Failed to generate a valid quiz question. Please try again.")
                        st.button("Try Again", on_click=lambda: st.session_state.pop("quiz_current_q_data", None))

            # Display the isolated Question UI
            if "quiz_current_q_data" in st.session_state:
                q_data = st.session_state.quiz_current_q_data
                q_params = st.session_state.quiz_params
                
                with st.container(border=True):
                    st.markdown(f"<div class='quiz-counter'>Question {st.session_state.quiz_current_q} of {q_params['num']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='quiz-question-text'>{q_data.get('question', 'Question text missing')}</div>", unsafe_allow_html=True)

                    if st.session_state.get("quiz_user_answer") is None:
                        for option in q_data.get('options',[]):
                            if st.button(option, use_container_width=True, key=f"q_opt_{option}"):
                                st.session_state.quiz_user_answer = option
                                st.rerun()
                    else:
                        user_ans = st.session_state.quiz_user_answer
                        is_correct = (user_ans == q_data.get('correct_answer'))
                        
                        if is_correct:
                            st.success(f"**Correct!** {q_data.get('explanation', '')}")
                            if st.session_state.quiz_bg != "correct":
                                st.session_state.quiz_score += 1
                                st.session_state.quiz_bg = "correct"
                                st.rerun()
                        else:
                            st.error(f"**Incorrect.** The correct answer was **{q_data.get('correct_answer')}**. \n\n*Explanation: {q_data.get('explanation', '')}*")
                            if st.session_state.quiz_bg != "wrong":
                                st.session_state.quiz_bg = "wrong"
                                st.rerun()

                        is_last_q = (st.session_state.quiz_current_q == q_params['num'])
                        if st.button("Next Question" if not is_last_q else "Finish Quiz", type="primary", use_container_width=True):
                            if is_last_q:
                                st.session_state.quiz_finished = True
                            else:
                                st.session_state.quiz_current_q += 1
                                st.session_state.pop("quiz_current_q_data", None) 
                            st.session_state.quiz_bg = "default" 
                            st.rerun()

            if st.session_state.get("quiz_finished"):
                score = st.session_state.quiz_score
                total = st.session_state.quiz_params['num']
                st.balloons()
                st.success(f"## 🎉 Quiz Complete! 🎉 \n\n### You scored: {score} / {total}")
                if st.button("Take Another Quiz", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        if key.startswith('quiz_'): del st.session_state[key]
                    st.rerun()

    # 💬 FULL MULTIMODAL AI CHAT MODE
    else:
        render_chat_interface = True

# ==========================================
# UNIVERSAL CHAT VIEW (AI Tutor / Teacher Chat)
# ==========================================
if render_chat_interface:
    st.markdown("<div class='big-title'>📚 helix.ai</div>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center; opacity: 0.60; font-size: 18px; margin-bottom: 30px;'>Your AI-powered Cambridge (CIE) Tutor for Grade 6-8. Master Math, Science, and English with deep, interactive learning.</div>", unsafe_allow_html=True)

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            disp = msg.get("content") or ""
            
            # Hide analytics and render text
            disp = re.sub(r"(?i)(?:Here is the )?(?:Analytics|JSON).*?(?:for student)?s?\s*[:-]?\s*", "", disp)
            disp = re.sub(r"===ANALYTICS_START===.*?===ANALYTICS_END===", "", disp, flags=re.IGNORECASE|re.DOTALL)
            disp = re.sub(r"```json\s*\{[^{]*?\"weak_point\".*?\}\s*```", "", disp, flags=re.IGNORECASE|re.DOTALL)
            disp = re.sub(r"\{[^{]*?\"weak_point\".*?\}", "", disp, flags=re.IGNORECASE|re.DOTALL)
            st.markdown(re.sub(r"\[PDF_READY\]", "", disp, flags=re.IGNORECASE).strip())
            
            # Render multimodal images generated during chat
            for img, mod in zip(msg.get("images") or[], msg.get("image_models", ["Unknown"]*10)):
                if img: st.image(img, use_container_width=True, caption=f"✨ Generated by helix.ai ({mod})")
            for b64, mod in zip(msg.get("db_images") or[], msg.get("image_models", ["Unknown"]*10)):
                if b64:
                    try: st.image(base64.b64decode(b64), use_container_width=True, caption=f"✨ Generated by helix.ai ({mod})")
                    except: pass
            
            # Render user file attachments
            if msg.get("user_attachment_bytes"):
                mime, name = msg.get("user_attachment_mime", ""), msg.get("user_attachment_name", "File")
                if "image" in mime: st.image(msg["user_attachment_bytes"], use_container_width=True)
                else: st.caption(f"📎 Attached: {name}")
            elif msg.get("user_attachment_b64"):
                try: st.image(base64.b64decode(msg["user_attachment_b64"]), use_container_width=True)
                except: st.caption(f"📎 Attached: {msg.get('user_attachment_name', 'File')}")
            elif msg.get("user_attachment_name"): st.caption(f"📎 Attached: {msg.get('user_attachment_name', 'File')}")

            # PDF Download Button
            if msg["role"] == "assistant" and msg.get("is_downloadable"):
                try: st.download_button("📄 Download PDF", data=create_pdf(msg.get("content") or "", msg.get("images") or[base64.b64decode(b) for b in msg.get("db_images", []) if b]), file_name=f"Paper_{idx}.pdf", mime="application/pdf", key=f"dl_{idx}")
                except Exception as e: st.error(f"PDF Error: {e}")

    if chat_input := st.chat_input("Ask Helix...", accept_file=True, file_type=["jpg","png","pdf","txt"]):
        if "textbook_handles" not in st.session_state: st.session_state.textbook_handles = upload_textbooks()
        
        f_bytes = chat_input.files[0].getvalue() if chat_input.files else None
        f_mime = chat_input.files[0].type if chat_input.files else None
        f_name = chat_input.files[0].name if chat_input.files else None
        
        # 🎯 FIX: .strip() removes Android/Samsung sticky keyboard spaces
        st.session_state.messages.append({"role": "user", "content": (chat_input.text or "").strip(), "user_attachment_bytes": f_bytes, "user_attachment_mime": f_mime, "user_attachment_name": f_name})
        save_chat_history(); st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        msg_data = st.session_state.messages[-1]
        with st.chat_message("assistant"):
            think = st.empty(); think.markdown("""<div class="thinking-container"><span class="thinking-text">Thinking</span><div class="thinking-dots"><div class="thinking-dot"></div><div class="thinking-dot"></div><div class="thinking-dot"></div></div></div>""", unsafe_allow_html=True)
            
            try:
                valid_history = []
                exp_role = "model"
                for m in reversed([m for m in st.session_state.messages[:-1] if not m.get("is_greeting")]):
                    r = "user" if m.get("role") == "user" else "model"
                    txt = m.get("content") or ""
                    if txt.strip() and r == exp_role:
                        valid_history.insert(0, types.Content(role=r, parts=[types.Part.from_text(text=txt)]))
                        exp_role = "user" if exp_role == "model" else "model"
                if valid_history and valid_history[0].role == "model": valid_history.pop(0)

                curr_parts =[]
                student_grade = st.session_state.get("active_grade", user_profile.get("grade", "Grade 6"))
                books = select_relevant_books(" ".join([m.get("content", "") for m in st.session_state.messages[-3:]]), st.session_state.textbook_handles, student_grade)
                
                if books:
                    for b in books: 
                        curr_parts.append(types.Part.from_text(text=f"--- START OF SOURCE TEXTBOOK: {b.display_name} ---"))
                        curr_parts.append(types.Part.from_uri(file_uri=b.uri, mime_type="application/pdf"))
                        curr_parts.append(types.Part.from_text(text=f"--- END OF SOURCE TEXTBOOK ---"))
                
                if f_bytes := msg_data.get("user_attachment_bytes"):
                    mime = msg_data.get("user_attachment_mime") or guess_mime(msg_data.get("user_attachment_name"))
                    if is_image_mime(mime): curr_parts.append(types.Part.from_bytes(data=f_bytes, mime_type=mime))
                    elif "pdf" in mime:
                        tmp = f"temp_{time.time()}.pdf"; open(tmp, "wb").write(f_bytes); up = client.files.upload_file(tmp)
                        while up.state.name == "PROCESSING": time.sleep(1); up = client.files.get(name=up.name)
                        curr_parts.append(types.Part.from_uri(file_uri=up.uri, mime_type="application/pdf")); os.remove(tmp)

                curr_parts.append(types.Part.from_text(text=f"Context: Student Grade is {student_grade}.\n\nUser Query: {msg_data.get('content')}"))
                resp = generate_with_retry("gemini-2.5-pro", valid_history +[types.Content(role="user", parts=curr_parts)], types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.3, tools=[{"google_search": {}}]))
                bot_txt = safe_response_text(resp) or "⚠️ *Failed to generate text.*"
                
                # Parse Hidden Analytics
                match_full = re.search(r"===ANALYTICS_START===(.*?)===ANALYTICS_END===", bot_txt, flags=re.IGNORECASE|re.DOTALL)
                if not match_full:
                    match_full = re.search(r"(?:(?:Here is the )?Analytics.*?:?\s*|```json\s*)?(\{[\s\S]*?\"weak_point\"[\s\S]*?\})(?:\s*```)?", bot_txt, flags=re.IGNORECASE)
                
                if match_full:
                    try:
                        ad = json.loads(match_full.group(1))
                        start_idx = match_full.start()
                        bot_txt = bot_txt[:start_idx].strip()
                        bot_txt = re.sub(r"(?i)(?:Here is the )?(?:Analytics|JSON).*?(?:for student)?s?\s*[:-]?\s*$", "", bot_txt).strip()
                        if is_authenticated and db: db.collection("users").document(user_email).collection("analytics").add({"timestamp": time.time(), **ad})
                    except Exception: pass

                think.empty()
                
                # Process visual requests (IMAGE_GEN / PIE_CHART)
                imgs, mods = [],[]
                if v_prompts := re.findall(r"(IMAGE_GEN|PIE_CHART):\s*\[(.*?)\]", bot_txt):
                    with concurrent.futures.ThreadPoolExecutor(5) as exe:
                        for r in exe.map(process_visual_wrapper, v_prompts):
                            if r and r[0]: imgs.append(r[0]); mods.append(r[1])
                
                dl = bool(re.search(r"\[PDF_READY\]", bot_txt, re.IGNORECASE) or (re.search(r"##\s*Mark Scheme", bot_txt, re.IGNORECASE) and re.search(r"\[\d+\]", bot_txt)))
                st.session_state.messages.append({"role": "assistant", "content": bot_txt, "is_downloadable": dl, "images": imgs, "image_models": mods})
                
                if is_authenticated and sum(1 for m in st.session_state.messages if m["role"] == "user") == 1:
                    t = generate_chat_title(client, st.session_state.messages)
                    if t: get_threads_collection().document(st.session_state.current_thread_id).set({"title": t}, merge=True)
                
                save_chat_history(); st.rerun()
                
            except Exception as e: think.empty(); st.error(f"Error: {e}")
