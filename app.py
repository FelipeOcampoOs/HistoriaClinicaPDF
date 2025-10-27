import os
import random
from io import BytesIO
from datetime import date

import streamlit as st
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

# --- Config de página (debe ir muy arriba) ---
st.set_page_config(page_title="Añadir hoja", page_icon="📄")
st.title("📄 Archivo")

# --- Estado inicial ---
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

# Diccionario para abreviaciones en español
MESES = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"
}

def init_math_captcha():
    if "captcha_a" not in st.session_state:
        st.session_state.captcha_a = random.randint(10, 99)
        st.session_state.captcha_b = random.randint(1, 9)

def render_math_captcha():
    init_math_captcha()
    a = st.session_state.captcha_a
    b = st.session_state.captcha_b
    st.sidebar.write(f"Resuelve: **{a} + {b} = ?**")
    return st.sidebar.text_input("Respuesta CAPTCHA", key="captcha_answer")

def reset_math_captcha():
    for k in ["captcha_a", "captcha_b", "captcha_answer"]:
        if k in st.session_state:
            del st.session_state[k]

def authenticate():
    """Login básico + CAPTCHA matemático con estado persistente."""
    # Si ya está autenticado, no muestres el formulario otra vez
    if st.session_state.get("auth_ok", False):
        st.sidebar.success("✅ Autenticado")
        if st.sidebar.button("Cerrar sesión"):
            for k in ("auth_ok", "captcha_a", "captcha_b", "captcha_answer"):
                st.session_state.pop(k, None)
            st.rerun()
        return True

    username = "fvlcic"
    password = "fvlcic2025"

    st.sidebar.subheader("Iniciar sesión")
    input_user = st.sidebar.text_input("Nombre de usuario", "")
    input_password = st.sidebar.text_input("Contraseña", type="password")
    ans = render_math_captcha()

    do_login = st.sidebar.button("Entrar", type="primary")
    if do_login:
        if input_user == username and input_password == password:
            try:
                if int(ans) == (st.session_state.captcha_a + st.session_state.captcha_b):
                    st.session_state.auth_ok = True
                    reset_math_captcha()
                    st.sidebar.success("✅ Autenticado correctamente")
                    st.rerun()  # redibuja ya logueado
                    return True
                else:
                    st.sidebar.error("❌ CAPTCHA incorrecto.")
                    reset_math_captcha()
                    return False
            except Exception:
                st.sidebar.error("❌ Ingresa un número válido en el CAPTCHA.")
                reset_math_captcha()
                return False
        else:
            st.sidebar.error("❌ Usuario o contraseña incorrectos.")
            return False
    return False

authenticated = authenticate()

# -------------------
# Lógica principal
# -------------------
if authenticated:
    uploaded = st.file_uploader("Sube tu PDF", type=["pdf"])

    def build_extra_page(page_size, firma_text, fecha_text, paginas_text) -> bytes:
        w, h = page_size
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))

        margin = 36
        y = h - margin

        c.setFont("Helvetica-Bold", 22)
        c.drawString(margin, y, "Certificado de copia")
        y -= 40

        c.setFont("Helvetica", 14)
        c.drawString(margin, y, f"FIRMA: {firma_text}"); y -= 28
        c.drawString(margin, y, f"FECHA: {fecha_text}"); y -= 28
        c.drawString(margin, y, f"NÚMERO DE PÁGINAS: {paginas_text}"); y -= 20

        c.showPage()
        c.save()
        buf.seek(0)
        return buf.read()

    def get_last_page_size(reader) -> tuple[float, float]:
        try:
            last = reader.pages[-1]
            return float(last.mediabox.width), float(last.mediabox.height)
        except Exception:
            return A4

    if not uploaded:
        st.info("Sube un PDF para comenzar.")
    else:
        pdf_bytes = uploaded.getvalue()
        try:
            reader = PdfReader(BytesIO(pdf_bytes))
        except Exception as e:
            st.error(f"❌ No se pudo leer el PDF: {e}")
            st.stop()

        if getattr(reader, "is_encrypted", False):
            st.error("🔒 Este PDF está protegido (encriptado). Desencríptalo antes de usarlo.")
            st.stop()

        num_pages_original = len(reader.pages)

        st.subheader("Datos para la hoja adicional")
        col1, col2 = st.columns(2)
        with col1:
            firma = st.text_input("FIRMA (puede dejarse en blanco)", value="")
        with col2:
            fecha_sel = st.date_input("FECHA", value=date.today())

        paginas_texto = st.text_input(
            "NÚMERO DE PÁGINAS (texto libre)",
            value=str(num_pages_original),
            placeholder=f"{num_pages_original} de {num_pages_original}",
            help="Puedes escribir '4 de 4', '436', etc. Solo se imprime como texto."
        )

        if st.button("Generar PDF con hoja final", type="primary"):
            try:
                fecha_str = fecha_sel.strftime("%d/%m/%Y")
                dia, mes, anio = fecha_str.split("/")
                mes_abrev = MESES.get(mes, mes)
                fecha_formateada = f"{dia}/{mes_abrev}/{anio}"

                w, h = get_last_page_size(reader)
                extra_bytes = build_extra_page(
                    (w, h),
                    firma_text=firma,
                    fecha_text=fecha_formateada,
                    paginas_text=paginas_texto.strip() or str(num_pages_original),
                )

                writer = PdfWriter()
                for p in reader.pages:
                    writer.add_page(p)

                extra_reader = PdfReader(BytesIO(extra_bytes))
                writer.add_page(extra_reader.pages[0])

                # Intenta conservar metadatos
                try:
                    if reader.metadata:
                        writer.add_metadata(reader.metadata)
                except Exception:
                    pass

                out = BytesIO()
                writer.write(out)
                out.seek(0)

                base = uploaded.name[:-4] if uploaded.name.lower().endswith(".pdf") else uploaded.name
                out_name = f"{base}_con_hoja_final.pdf"

                st.success("✅ PDF generado correctamente.")
                st.download_button(
                    label="⬇️ Descargar PDF final",
                    data=out,
                    file_name=out_name,
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"❌ Ocurrió un error al generar el PDF: {e}")
else:
    st.info("Debes iniciar sesión para acceder al contenido.")
