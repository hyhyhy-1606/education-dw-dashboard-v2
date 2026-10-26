import streamlit as st
import pandas as pd
from pathlib import Path
import json
import uuid
import datetime

st.set_page_config(page_title='Education DW BI — Cloud & Local', layout='wide', page_icon='🎓')

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / 'data' / 'silver'
PROJECT = 'data-warehouse-512306'
DATASET = 'education_dw'

# ─── BigQuery client (cached) ─────────────────────────────────────────────────
# Cloud mode is enabled only when Streamlit Secrets contains a service-account
# configuration. Never commit a JSON key file to the repository.
@st.cache_resource
def get_bq_client():
    try:
        credentials_info = dict(st.secrets["gcp_service_account"])
        from google.oauth2 import service_account
        from google.cloud import bigquery
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info
        )
        return bigquery.Client(
            credentials=credentials,
            project=PROJECT,
            location="asia-southeast1",
        )
    except Exception:
        return None

def bq_available():
    return get_bq_client() is not None

def run_sql(sql):
    """Run a DDL/CREATE OR REPLACE statement on BigQuery (Sandbox-compatible)."""
    client = get_bq_client()
    job = client.query(sql)
    job.result()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
st.sidebar.title("☁️ Google Cloud & Data")
if bq_available():
    st.sidebar.success(
        f"**GCP Project:** `{PROJECT}`\n\n"
        "**Region:** `asia-southeast1` (Singapore)\n\n"
        f"**Dataset:** `{DATASET}` & `education_dw_gold`"
    )
else:
    st.sidebar.error("Chưa tìm thấy `gcp_key.json`.\nDùng chế độ Local.")

data_source = st.sidebar.radio(
    "Nguồn dữ liệu:",
    ("☁️ Google BigQuery Cloud (Live)", "💾 Local Silver (Offline)"),
    index=1
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Làm mới dữ liệu", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if bq_available():
    if st.sidebar.button("💾 Đồng bộ Cloud → Local", use_container_width=True):
        client = get_bq_client()
        mapping = [
            ('silver_leads', 'leads_clean.csv'),
            ('silver_students', 'students_clean.csv'),
            ('silver_enrollments', 'enrollments_clean.csv'),
            ('silver_learning_records', 'learning_records_clean.csv'),
            ('silver_career_guidance', 'career_guidance_clean.csv'),
            ('silver_campaigns', 'campaigns_clean.csv'),
            ('silver_courses', 'courses_clean.csv'),
        ]
        with st.sidebar:
            prog = st.progress(0, text="Đang đồng bộ...")
            for i, (tbl, fname) in enumerate(mapping):
                df_s = client.query(f"SELECT * FROM `{PROJECT}.{DATASET}.{tbl}`").to_dataframe()
                df_s.to_csv(DATA_DIR / fname, index=False)
                prog.progress((i + 1) / len(mapping), text=f"Đồng bộ {fname}...")
            prog.empty()
        st.cache_data.clear()
        st.sidebar.success("✅ Đồng bộ hoàn tất!")
        st.rerun()

# ─── Load data ───────────────────────────────────────────────────────────────
def load_local_csv(name):
    path = DATA_DIR / name
    if not path.exists():
        st.error(f'Không tìm thấy {path}.')
        st.stop()
    return pd.read_csv(path)

@st.cache_data(ttl=120)
def load_all(source):
    if source == "☁️ Google BigQuery Cloud (Live)" and bq_available():
        c = get_bq_client()
        try:
            students   = c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_students`").to_dataframe()
            leads      = c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_leads`").to_dataframe()
            enrollments= c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_enrollments`").to_dataframe()
            learning   = c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_learning_records`").to_dataframe()
            guidance   = c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_career_guidance`").to_dataframe()
            campaigns  = c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_campaigns`").to_dataframe()
            courses    = c.query(f"SELECT * FROM `{PROJECT}.{DATASET}.silver_courses`").to_dataframe()
            return students, leads, enrollments, learning, guidance, campaigns, courses, True
        except Exception as e:
            st.warning(f"⚠️ Lỗi BigQuery: {e}. Dùng Local.")

    students    = load_local_csv('students_clean.csv')
    leads       = load_local_csv('leads_clean.csv')
    enrollments = load_local_csv('enrollments_clean.csv')
    learning    = load_local_csv('learning_records_clean.csv')
    guidance    = load_local_csv('career_guidance_clean.csv')
    campaigns   = load_local_csv('campaigns_clean.csv')
    courses     = load_local_csv('courses_clean.csv')
    return students, leads, enrollments, learning, guidance, campaigns, courses, False

students, leads, enrollments, learning, guidance, campaigns, courses, is_live = load_all(data_source)

# ─── MAIN ────────────────────────────────────────────────────────────────────
st.title('EduMarketing 360° — Marketing Performance Dashboard')
if is_live:
    st.success(f"🟢 **Live BigQuery** | `{PROJECT}` | `{DATASET}` | `asia-southeast1`")
else:
    st.info("📦 **Chế độ:** Local Silver (Offline)")

st.caption("Quản trị vòng đời học viên — Marketing · Tuyển sinh · Doanh thu · Học tập · Hướng nghiệp")
st.caption("Bản triển khai Community Cloud: mặc định Local Silver; thao tác ghi BigQuery bị vô hiệu hóa để tránh ghi đè dữ liệu.")

# ── KPI Top ──────────────────────────────────────────────────────────────────
lead_total = len(leads)
converted  = int((leads['lead_status'] == 'Converted').sum())
conversion = converted / lead_total if lead_total else 0
recognized = enrollments.loc[~enrollments.enrollment_status.isin(['Cancelled','Refunded']), 'amount_paid_vnd'].sum()
attendance = (learning.attendance_status == 'Present').mean() if len(learning) else 0
total_students = len(students)
total_enroll   = len(enrollments)

k1, k2, k3 = st.columns(3)

k1.metric('👥 Học viên', f'{total_students:,}')
k2.metric('📋 Đăng ký', f'{total_enroll:,}')
k3.metric('📣 Leads', f'{lead_total:,}')

k4, k5, k6 = st.columns(3)

k4.metric('✅ Chuyển đổi', f'{converted:,}')
k5.metric('📊 Tỷ lệ CĐ', f'{conversion:.1%}')
k6.metric(
    '💰 Doanh thu (VND)',
    f'{recognized:,.0f}',
    help=f'Doanh thu đầy đủ: {recognized:,.0f} VND'
)

st.markdown("---")

# ─── TABS ────────────────────────────────────────────────────────────────────
tab_dash, tab_form_student, tab_form_enroll, tab_form_lead = st.tabs([
    "📊 Dashboard", "➕ Thêm học viên mới", "📝 Đăng ký khóa học", "📣 Thêm Lead mới"
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    # Marketing
    st.subheader('📈 1. Marketing & Tuyển sinh')
    camp_summary = campaigns.merge(
        leads.groupby('campaign_id').agg(total_leads=('lead_id','nunique')).reset_index(),
        on='campaign_id', how='left'
    )
    camp_summary['total_leads'] = camp_summary['total_leads'].fillna(0)
    cm1, cm2 = st.columns([3,2])
    with cm1:
        st.markdown("**Leads theo chiến dịch**")
        st.bar_chart(camp_summary.set_index('campaign_name')['total_leads'])
    with cm2:
        st.markdown("**Ngân sách & hiệu quả kênh**")
        st.dataframe(camp_summary[['campaign_name','channel','marketing_spend','total_leads']], use_container_width=True)

    st.markdown("---")

    # Enrollment & Revenue
    st.subheader('💰 2. Tuyển sinh & Doanh thu')
    rev = enrollments.copy()
    rev['recognized_revenue_vnd'] = rev['amount_paid_vnd'].where(
        ~rev.enrollment_status.isin(['Cancelled','Refunded']), 0)
    cr1, cr2 = st.columns([3,2])
    with cr1:
        st.markdown("**Doanh thu theo môn học (VND)**")
        st.bar_chart(rev.groupby('course_name')['recognized_revenue_vnd'].sum())
    with cr2:
        st.markdown("**Cơ cấu trạng thái đăng ký**")
        st.dataframe(
            rev.groupby(['course_name','enrollment_status']).agg(
                dk=('enrollment_id','nunique'), rev=('recognized_revenue_vnd','sum')
            ).reset_index(), use_container_width=True)

    st.markdown("---")

    # Learning
    st.subheader('🎓 3. Học tập & Đào tạo')
    cl1, cl2 = st.columns(2)
    cl1.metric('Tỷ lệ điểm danh', f'{attendance:.1%}')
    cl2.metric('Điểm TB', f'{learning.assessment_score.mean():.2f}/10')
    st.bar_chart(learning.groupby('course_id')['assessment_score'].mean())

    st.markdown("---")

    # Career Guidance
    st.subheader('🧭 4. Tư vấn Hướng nghiệp')
    cg1, cg2 = st.columns([3,2])
    with cg1:
        st.bar_chart(guidance['guidance_type'].value_counts())
    with cg2:
        st.dataframe(
            guidance.groupby('outcome').agg(
                sessions=('guidance_id','count'),
                avg_sat=('satisfaction_score','mean')
            ).reset_index(), use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — THÊM HỌC VIÊN MỚI
# ═══════════════════════════════════════════════════════════════════════════════
with tab_form_student:
    st.subheader("➕ Nhập thông tin học viên mới")
    st.info("Bản dành cho nhân viên hiện ở chế độ chỉ đọc để bảo vệ dữ liệu Silver. Chức năng ghi dữ liệu lên BigQuery đã được tắt.")

    with st.form("form_add_student", clear_on_submit=True):
        fa1, fa2 = st.columns(2)
        with fa1:
            s_gender = st.selectbox("Giới tính", ["Nam", "Nữ", "Chưa xác định"])
            s_dob    = st.date_input("Ngày sinh", value=datetime.date(2008, 1, 1),
                                     min_value=datetime.date(1995,1,1),
                                     max_value=datetime.date(2012,12,31))
        with fa2:
            s_grade   = st.selectbox("Khối lớp", [10, 11, 12])
            s_district= st.text_input("Quận/Huyện", placeholder="Ví dụ: Quận 1")
            s_school  = st.text_input("Mã trường (tuỳ chọn)", placeholder="Ví dụ: SCH_001")

        submitted_student = st.form_submit_button("💾 Lưu học viên lên BigQuery", use_container_width=True, type="primary", disabled=True)

    if submitted_student:
        if not s_district.strip():
            st.error("Vui lòng nhập Quận/Huyện!")
        elif not is_live:
            st.error("⚠️ Cần kết nối BigQuery Cloud để lưu. Đổi sang chế độ Live.")
        else:
            new_id = 'STU_' + uuid.uuid4().hex[:6].upper()
            school_id = s_school.strip() if s_school.strip() else 'SCH_UNKNOWN'
            sql = f"""
            CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.silver_students` AS
            SELECT * FROM `{PROJECT}.{DATASET}.silver_students`
            UNION ALL
            SELECT
              '{new_id}' AS student_id,
              '{s_gender}' AS gender,
              DATE '{s_dob.strftime('%Y-%m-%d')}' AS date_of_birth,
              '{s_grade}' AS grade,
              '{school_id}' AS school_id,
              '{s_district.strip()}' AS district,
              CURRENT_TIMESTAMP() AS created_at
            """
            try:
                with st.spinner("Đang lưu lên BigQuery..."):
                    run_sql(sql)
                st.success(f"✅ Đã thêm học viên **{new_id}** thành công! Bấm **🔄 Làm mới dữ liệu** ở thanh bên để cập nhật Dashboard.")
                st.balloons()
            except Exception as e:
                st.error(f"Lỗi: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ĐĂNG KÝ KHÓA HỌC
# ═══════════════════════════════════════════════════════════════════════════════
with tab_form_enroll:
    st.subheader("📝 Đăng ký khóa học cho học viên")
    st.info("Bản dành cho nhân viên hiện ở chế độ chỉ đọc để bảo vệ dữ liệu Silver. Chức năng ghi dữ liệu lên BigQuery đã được tắt.")

    # Load student list for selection
    student_options = students['student_id'].tolist()
    course_options  = {row['course_name']: (row['course_id'], row['standard_fee_vnd'])
                       for _, row in courses.iterrows()}

    with st.form("form_add_enrollment", clear_on_submit=True):
        fe1, fe2 = st.columns(2)
        with fe1:
            e_student    = st.selectbox("Mã học viên", student_options)
            e_course_name= st.selectbox("Khóa học", list(course_options.keys()))
            e_status     = st.selectbox("Trạng thái", ["Confirmed", "Waitlisted", "Pending"])
        with fe2:
            e_campaign   = st.selectbox("Chiến dịch Marketing", campaigns['campaign_id'].tolist())
            e_date       = st.date_input("Ngày đăng ký", value=datetime.date.today())
            e_discount   = st.number_input("Giảm giá (VND)", min_value=0, value=0, step=100000)

        # Auto-fill price based on course selection
        st.markdown("*(Học phí niêm yết sẽ tự động điền theo môn học được chọn)*")
        submitted_enroll = st.form_submit_button("💾 Lưu đăng ký lên BigQuery", use_container_width=True, type="primary", disabled=True)

    if submitted_enroll:
        if not is_live:
            st.error("⚠️ Cần kết nối BigQuery Cloud để lưu.")
        else:
            course_id, list_price = course_options[e_course_name]
            amount_paid = max(0, list_price - e_discount)
            new_eid = 'ENR_' + uuid.uuid4().hex[:8].upper()
            sql = f"""
            CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.silver_enrollments` AS
            SELECT * FROM `{PROJECT}.{DATASET}.silver_enrollments`
            UNION ALL
            SELECT
              '{new_eid}' AS enrollment_id,
              '{e_student}' AS student_id,
              NULL AS lead_id,
              '{e_campaign}' AS campaign_id,
              '{course_id}' AS course_id,
              '{e_course_name}' AS course_name,
              DATE '{e_date.strftime('%Y-%m-%d')}' AS enrollment_date,
              '{e_status}' AS enrollment_status,
              {float(list_price)} AS list_price_vnd,
              {float(e_discount)} AS discount_vnd,
              {float(amount_paid)} AS amount_paid_vnd
            """
            try:
                with st.spinner("Đang lưu lên BigQuery..."):
                    run_sql(sql)
                st.success(
                    f"✅ Đã đăng ký **{e_course_name}** cho học viên **{e_student}**!\n\n"
                    f"- Mã đăng ký: `{new_eid}`\n"
                    f"- Học phí niêm yết: **{list_price:,.0f} VND**\n"
                    f"- Giảm giá: **{e_discount:,.0f} VND**\n"
                    f"- **Doanh thu ghi nhận: {amount_paid:,.0f} VND**\n\n"
                    f"👉 Bấm **🔄 Làm mới dữ liệu** ở thanh bên để xem Dashboard cập nhật!"
                )
                st.balloons()
            except Exception as e:
                st.error(f"Lỗi: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — THÊM LEAD MỚI
# ═══════════════════════════════════════════════════════════════════════════════
with tab_form_lead:
    st.subheader("📣 Ghi nhận khách hàng tiềm năng (Lead) mới")
    st.info("Nhập thử thông tin Lead tại giao diện. Chức năng lưu lên BigQuery đã được tắt trong bản trực quan hóa nội bộ để bảo vệ dữ liệu.")

    with st.form("form_add_lead", clear_on_submit=True):
        fl1, fl2 = st.columns(2)
        with fl1:
            l_student   = st.selectbox("Học viên liên quan", ["(Khách mới, chưa có trong hệ thống)"] + student_options)
            l_source    = st.selectbox("Nguồn Lead", ["Facebook Ads", "Google Ads", "Zalo Ads", "Website", "Referral (Giới thiệu)", "Hotline", "Khác"])
            l_status    = st.selectbox("Trạng thái Lead", ["New", "Contacted", "Qualified", "Converted", "Lost"])
        with fl2:
            l_campaign  = st.selectbox("Chiến dịch Marketing", campaigns['campaign_id'].tolist())
            l_date      = st.date_input("Ngày phát sinh Lead", value=datetime.date.today())
            l_attempts  = st.number_input("Số lần đã liên hệ", min_value=0, max_value=50, value=1)
            l_hours     = st.number_input("Thời gian phản hồi đầu (giờ)", min_value=0.0, max_value=72.0, value=2.0, step=0.5)

        submitted_lead = st.form_submit_button("💾 Lưu Lead lên BigQuery", use_container_width=True, type="primary", disabled=True)

    if submitted_lead:
        if not is_live:
            st.error("⚠️ Cần kết nối BigQuery Cloud để lưu.")
        else:
            new_lid = 'LEAD_' + uuid.uuid4().hex[:8].upper()
            student_val = 'NULL' if l_student.startswith('(') else f"'{l_student}'"
            sql = f"""
            CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.silver_leads` AS
            SELECT * FROM `{PROJECT}.{DATASET}.silver_leads`
            UNION ALL
            SELECT
              '{new_lid}' AS lead_id,
              {student_val} AS student_id,
              '{l_campaign}' AS campaign_id,
              DATE '{l_date.strftime('%Y-%m-%d')}' AS lead_created_date,
              '{l_source}' AS lead_source,
              '{l_status}' AS lead_status,
              {l_attempts} AS contact_attempts,
              {l_hours} AS first_response_hours
            """
            try:
                with st.spinner("Đang lưu lên BigQuery..."):
                    run_sql(sql)
                st.success(
                    f"✅ Đã ghi nhận Lead mới **{new_lid}**!\n\n"
                    f"- Nguồn: **{l_source}** | Chiến dịch: **{l_campaign}**\n"
                    f"- Trạng thái: **{l_status}**\n\n"
                    f"👉 Bấm **🔄 Làm mới dữ liệu** để xem tổng số Leads và tỷ lệ chuyển đổi cập nhật!"
                )
                st.balloons()
            except Exception as e:
                st.error(f"Lỗi: {e}")
