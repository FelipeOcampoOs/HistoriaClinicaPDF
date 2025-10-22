import os
from io import BytesIO
from datetime import date

import streamlit as st
import streamlit.components.v1 as components
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import requests

# Diccionario para abreviaciones en español
MESES = {
    "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr",
    "05": "May", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"
}

# Configuración de la página
st.set_page_config(page_title="Añadir hoja", page_icon="📄")
st.title("📄 Archivo")

# --- reCAPTCHA: HTML widget que retorna el token a Python ---
def recaptcha_widget():
    """
    Renderiza el reCAPTCHA v2 (checkbox) y retorna el token cuando el usuario lo resuelve.
    Requiere RECAPTCHA_SITE_KEY en st.secrets o variable de entorno.
    """
    site_key = "6LeIffMrAAAAAEPA2Li90eU-nFNz4WX7WiaIXbfZ"
    if not site_key:
        st.sidebar.warning("⚠️ Falta RECAPTCHA_SITE_KEY en Secrets o variables de entorno.")
        return None

    html_code = f"""
    <div id="recaptcha" style="transform:scale(1);transform-origin:0 0;"></div>
    <script>
      var recaptcha_loaded = false;
      function onloadCallback() {{
        if (recaptcha_loaded) return;
        recaptcha_loaded = true;
        grecaptcha.render('recaptcha', {{
          'sitekey': '{site_key}',
          'callback': function(token) {{
            // Enviar el token a Streamlit (components.html devuelve este valor)
            if (window.parent && window.parent.Streamlit) {{
              window.parent.Streamlit.setComponentValue(token);
            }}
          }}
        }});
      }}
    </script>
    <script src="https://www.google.com/recaptcha/api.js?onload=onloadCallback&render=explicit" async defer></script>
    """
    # El valor retornado será el "token" cuando el usuario resuelve el captcha
    token = components.html(html_code, height=90)
    return token

def verify_recaptcha(token: str) -> bool:
    """Verifica el token de reCAPTCHA v2 con Google."""
    secret = "6LeIffMrAAAAAGFfb7cmZd4HVr3qG27kNLfcGGo1"
    if not secret:
        st.sidebar.warning("⚠️ Falta RECAPTCHA_SECRET_KEY en Secrets o variables de entorno.")
        return False
    if not token:
        return False
    try:
        resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token},
            timeout=5
        )
        data = resp.json()
        return bool(data.get("success"))
    except Exception as e:
        st.sidebar.error(f"No se pudo verificar el reCAPTCHA: {e}")
        return False

# Función de autenticación
def authenticate():
    """Autenticación básica + reCAPTCHA v2."""
    username = "usuario"
    password = "contraseña123"

    st.sidebar.subheader("Iniciar sesión")
    input_user = st.sidebar.text_input("Nombre de usuario", "")
    input_password = st.sidebar.text_input("Contraseña", type="password")

    # Widget reCAPTCHA (devuelve token cuando se resuelve)
    token = recaptcha_widget()

    do_login = st.sidebar.button("Entrar", type="primary")

    if do_login:
        if input_user == username and input_password == password:
            if token and verify_recaptcha(token):
                st.sidebar.success("✅ Autenticado correctamente")
                return True
            else:
                st.sidebar.error("❌ Verifica el CAPTCHA para continuar.")
                return False
        else:
            st.sidebar.error("❌ Usuario o contraseña incorrectos.")
            return False

    return False

# Comprobamos si el usuario está autenticado
authenticated = authenticate()

# Si el usuario está autenticado, se muestra el contenido principal
if authenticated:
    uploaded = st.file_uploader("Sube tu PDF", type=["pdf"])

    def build_extra_page(page_size, firma_text, fecha_text, paginas_text) -> bytes:
        """Genera una página PDF (bytes) con los campos solicitados."""
        w, h = page_size
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(w, h))

        margin = 36  # ~0.5"
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
        """Obtiene el tamaño (w, h) de la última página, o A4 si falla."""
        try:
            last = reader.pages[-1]
            return float(last.mediabox.width), float(last.mediabox.height)
        except Exception:
            return A4

    if uploaded:
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
        st.info("Sube un PDF para comenzar.")
else:
    st.info("Debes iniciar sesión para acceder al contenido.")
