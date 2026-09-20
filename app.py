"""Community Cloud entrypoint. Only synthetic inputs are cached across sessions."""
from dataclasses import asdict, replace
import io
import json
import os
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
from tips_abm.config import Config, policy_grid
from tips_abm.data import Bundle, prepare_excel
from tips_abm.calibration import calibrate
from tips_abm.experiments import presets, variants, run_batch, replay
from tips_abm.reporting import export_zip

st.set_page_config(page_title="TIPS Policy Lab", page_icon="◈", layout="wide")
st.markdown("""<style>.block-container{padding-top:2rem;max-width:1440px}h1{letter-spacing:-1px}
div[data-testid="stMetric"]{background:#f1f7f6;border-radius:12px;padding:18px}
.eyebrow{font-size:12px;letter-spacing:3px;color:#127b72;font-weight:700}</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def public_bundle(threshold):
    return Bundle.load("synthetic", threshold)


def upload_enabled():
    if os.environ.get("ENABLE_PRIVATE_UPLOAD", "false").lower() == "true":
        return True
    try:
        return bool(st.secrets.get("ENABLE_PRIVATE_UPLOAD", False))
    except (FileNotFoundError, KeyError):
        return False


def line(frame, y, title):
    st.altair_chart(alt.Chart(frame).mark_line().encode(x=alt.X("year:Q", title="가상 연도"), y=y,
        color="series:N", tooltip=list(frame.columns)).properties(title=title), use_container_width=True)


with st.sidebar:
    st.markdown("### 실험 설정")
    threshold = st.selectbox("매출 기준", [1000.0, 500.0, 2000.0], help="연구용 재무상태 구분입니다. 공식 TIPS 성공 판정 기준과 다릅니다.")
    st.caption("합성자료: 임의 화폐단위 · 실제 자료: 백만원")
    bundle = public_bundle(threshold)
    if upload_enabled():
        st.caption("Excel은 클라우드 서버에서 처리됩니다. 해당 서버에서의 연구자료 처리가 허용된 경우 사용하세요.")
        upload = st.file_uploader("2024 TIPS 원본 Excel", type=["xlsx"])
        strict = st.checkbox("재무 세 항목 동시 0을 불명으로 처리")
        if upload is not None and st.button("업로드 자료 적용"):
            try:
                with st.spinner("Excel을 읽고 관측 패턴을 구성합니다…"):
                    panel, metadata = prepare_excel(io.BytesIO(upload.getvalue()), None, strict)
                    st.session_state["private_bundle"] = Bundle(panel, metadata, threshold, strict)
                    for key in ("result", "calibration", "replay"):
                        st.session_state.pop(key, None)
            except Exception as exc:
                st.error(f"자료를 읽지 못했습니다: {exc}")
        if "private_bundle" in st.session_state:
            if st.button("업로드 자료 지우기"):
                for key in ("private_bundle", "result", "calibration", "replay"):
                    st.session_state.pop(key, None)
                st.rerun()
            bundle = st.session_state["private_bundle"]
            if bundle.threshold != threshold:
                st.warning("매출 기준이 바뀌었습니다. 업로드 자료 적용을 다시 누르세요.")
                st.stop()
    else:
        st.caption("공개 기본값은 합성자료입니다. 실제 Excel 처리는 배포 설정에서 활성화할 수 있습니다.")
    operators = st.slider("운영사 수", 4, 20, 8)
    slots = st.slider("연간 추천권", 20, 160, 40, step=20)
    cohorts = st.slider("정책 적용 코호트", 3, 10, 6)
    horizon = st.slider("기업별 추적 기간", 5, 10, 8)
    repetitions = st.slider("독립 반복", 2, 10, 3)
    seed = st.number_input("난수 시드", 0, 2147483647, 20260920)
    with st.expander("행동·관측 가정"):
        adaptation = st.slider("평가 유인 반응", 0.0, 2.0, 1.0, .25)
        support_effect = st.slider("지원 효과 · 가정값", 0.0, .5, .25, .05)
        correlation = st.select_slider("잠재력–사업화 지연 상관", [-.5, 0.0, .5], 0.0)
        misclassification = st.slider("속도 오분류율", 0.0, .5, .25, .05)
        missing = st.slider("정부의 연간 관측 누락률", 0.0, .5, .1, .05)
        unknown = st.select_slider("불명 사례 점수", [0.0, .5, 1.0], .5)
        erase = st.checkbox("퇴출 후 과거 평가기록 소실")
        metric = st.selectbox("단기 평가 지표", ["revenue", "profit", "sustained_profit"], format_func=lambda v: {"revenue": "매출 기준 달성", "profit": "영업흑자", "sustained_profit": "연속 2년 영업흑자"}[v])
    cfg = Config(operators=operators, slots=slots, cohorts=cohorts, horizon=horizon, seed=int(seed),
                 adaptation=adaptation, support_effect=support_effect, quality_delay=correlation,
                 misclassification=misclassification, online_missing=missing, unknown_credit=unknown,
                 erase_after_exit=erase, metric=metric, threshold=threshold)

st.markdown('<div class="eyebrow">TIPS POLICY LAB · RESEARCH EDITION</div>', unsafe_allow_html=True)
st.title("평가를 바꾸면, 어떤 기업이 기회를 얻을까?")
st.write("평가 시점 → 운영사 추천권 → 기업 선택과 지원 → 장기 경제성과")
st.info("합성자료 시연입니다. 실제 TIPS 성과·정책 효과의 추정 결과가 아닙니다." if bundle.metadata.get("synthetic")
        else "실제 선정기업의 관측 패턴을 사용합니다. 신청·탈락기업 비교가 없어 TIPS의 인과적 효과는 식별하지 않습니다.")
tab_design, tab_data, tab_cal, tab_exp, tab_result, tab_docs = st.tabs(
    ["연구 질문", "① 자료 점검", "② 모형 보정", "③ 정책 실험", "④ 결과 비교", "ODD · 재현"])

with tab_design:
    st.subheader("정책 결정은 무엇이 달라지나?")
    a, b, c = st.columns(3)
    a.markdown("#### 언제 평가할 것인가\n공통 2·3·5년 평가와, 관측한 사업화 속도에 따른 차등 평가를 비교합니다.")
    b.markdown("#### 얼마나 배분을 바꿀 것인가\n점수가 낮은 운영사의 추천권을 빠르게 줄이는 방식과 완만하게 조정하는 방식을 비교합니다.")
    c.markdown("#### 불확실성을 어떻게 다룰 것인가\n정보 누락, 실패 기록, 탐색 몫이 장기 성과와 기회 배분을 어떻게 바꾸는지 봅니다.")
    st.markdown("**공통 장기 기준:** 같은 약정예산 아래 누적 영업이익과 연속 2년 흑자 달성 기업 수. 매출·퇴출·집중도·지연형 기업 비중은 별도 보고합니다.")
    st.caption("누적 영업이익은 기업가치·EBITDA·투자수익률과 다릅니다. 미관측 EBITDA나 멀티플을 임의로 만들지 않습니다.")
    st.dataframe(pd.DataFrame([
        ["E1 고정경로", "관측 성과 고정, 평가와 가상 배분 변경", "측정·배분의 기계적 변화"],
        ["E3 ABM 정책", "운영사의 기업 선택과 지원도 변화", "메커니즘 아래 조건부 결과"],
        ["E4–E6", "행동·구조·정보 가정 변경", "정책 순위가 뒤집히는 조건"]], columns=["분석", "변경", "해석"]), hide_index=True, use_container_width=True)

with tab_data:
    p = bundle.panel
    st.subheader("관측 범위와 결측부터 확인")
    a, b, c = st.columns(3)
    a.metric("기업 수", f"{p.id.nunique():,}")
    b.metric("재무연도", f"{int(p.year.min())}–{int(p.year.max())}")
    c.metric("자료 구분", "합성" if bundle.metadata.get("synthetic") else "실제 · 세션 전용")
    coverage = p.groupby(["co", "age"]).agg(기업=("id", "size"), 매출관측=("rev", "count"), 이익관측=("profit", "count"), 기록폐업=("closed", "sum")).reset_index()
    st.dataframe(coverage, hide_index=True, use_container_width=True, height=260)
    st.caption("선정 전 기간은 제외합니다. 기록폐업과 재무 결측을 구분합니다. 폐업 미기록을 확인된 생존으로 해석하지 않습니다.")
    with st.expander("입력 출처·처리 내역"):
        st.json(bundle.metadata)
    if st.button("E1 · 고정경로 재평가"):
        st.session_state["replay"] = replay(bundle, cfg)
    if "replay" in st.session_state:
        fixed = st.session_state["replay"]
        hhi = fixed.groupby(["policy", "year"]).weight.apply(lambda a: (a * a).sum()).reset_index(name="HHI")
        hhi["series"] = hhi.policy
        line(hhi, "HHI:Q", "고정 성과경로의 가상 추천권 집중도")
        st.download_button("고정경로 배분표 CSV", fixed.to_csv(index=False).encode("utf-8-sig"), "fixed_path_replay.csv")

with tab_cal:
    st.subheader("자료와 양립하는 모수 집합을 남깁니다")
    st.write("2019년 이전 선정기업 h=0–2의 상태·전이·재무분포·0·폐업·결측 패턴을 맞춥니다. 정책 우열은 보정 목표가 아닙니다.")
    st.caption("h=3–5와 최근 코호트는 이전 가능성 진단용입니다. 이미 검토한 데이터이므로 미열람 확증 표본이라고 부르지 않습니다.")
    a, b = st.columns(2)
    candidates = a.slider("보정 후보 수 · Cloud 시연", 4, 16, 8, step=4)
    tolerance = b.slider("각 패턴군 허용 RMSE", .5, 3.0, 1.5, .25)
    st.caption("Cloud 보정은 후보당 2회 반복하는 시연 설정입니다. 논문용 보정은 CLI에서 규모를 늘리고 기준을 먼저 동결하세요.")
    if st.button("E2 · 보정 실행"):
        bar = st.progress(0.0)
        try:
            cal = calibrate(bundle, cfg, candidates, 2, tolerance, progress=lambda d, n, _: bar.progress(d / n))
            cal.update(input_hash=bundle.hash, ui_config=asdict(cfg))
            st.session_state["calibration"] = cal
        except Exception as exc:
            st.error(f"보정을 완료하지 못했습니다: {exc}")
    cal = st.session_state.get("calibration")
    if cal:
        st.metric("허용 모수 집합", len(cal["accepted"]))
        st.dataframe(cal["trials"], hide_index=True, use_container_width=True)
        if not cal["accepted"]:
            st.warning("통과한 모수가 없습니다. 현재 보정 결과로 정책을 권고할 수 없습니다. 자료·모형·기준을 재검토하고 변경 이력을 남기세요.")
        st.download_button("보정 명세·허용 집합 JSON", json.dumps({"accepted": cal["accepted"], "specification": cal["specification"]}, ensure_ascii=False, indent=2), "accepted.json")
        st.download_button("전체 보정 손실 CSV", cal["discrepancies"].to_csv(index=False).encode("utf-8-sig"), "calibration_discrepancies.csv")

with tab_exp:
    st.subheader("같은 예산·후보군 아래 정책 비교")
    labels = {"main": "E3 주분석", "ablation": "E4 메커니즘 제거", "sensitivity": "E5 한 요인 민감도", "information": "E6 정보 개선"}
    family = st.selectbox("실험 종류", list(labels), format_func=labels.get)
    all_policies = policy_grid() if st.checkbox("37개 전체 정책 조합") else presets()
    names = [p.name for p in all_policies if p.name != "fixed"]
    selected = st.multiselect("비교 정책 · fixed 기준은 항상 포함", names, default=names[:3])
    policies = [p for p in all_policies if p.name == "fixed" or p.name in selected]
    worlds = variants(cfg, family)
    chosen = st.multiselect("구조 조건", [w for w, _ in worlds], default=[w for w, _ in worlds][:2])
    worlds = [(w, c) for w, c in worlds if w in chosen]
    use_cal = st.checkbox("허용 모수 집합 사용 · 주분석", disabled=family != "main") and family == "main"
    compatible = bool(cal and cal.get("input_hash") == bundle.hash and cal.get("ui_config") == asdict(cfg) and cal["accepted"])
    if use_cal and not compatible:
        st.warning("현재 자료·설정과 일치하는 허용 모수가 없습니다. ②에서 보정하세요.")
    jobs = ([(w, a["id"], replace(c, **a["parameters"])) for w, c in worlds for a in cal["accepted"]]
            if use_cal and compatible else [] if use_cal else [(w, "uncalibrated", c) for w, c in worlds])
    count = len(jobs) * len(policies) * repetitions
    work = sum(c.slots * (c.warmup + c.cohorts) * (c.horizon + 1) for _, _, c in jobs) * len(policies) * repetitions
    st.write(f"**실행 {count:,}회** · 같은 반복 번호의 후보·충격을 공유합니다.")
    st.caption("화면 실행 한도: 120회·기업-연도 예산 2,000,000. 대규모 실행은 CLI를 사용합니다. 미보정 실행은 구조 탐색이며 지원 효과는 가정값입니다.")
    st.dataframe(pd.DataFrame([asdict(p) for p in policies]), hide_index=True, use_container_width=True)
    if st.button("선택한 실험 실행", type="primary", disabled=not jobs or count > 120 or work > 2_000_000):
        bar = st.progress(0.0)
        try:
            tables, meta = run_batch(bundle, jobs, policies, repetitions, progress=lambda d, n: bar.progress(d / n))
            meta["experiment_family"] = family
            st.session_state["result"] = (tables, meta)
            st.success("실행을 마쳤습니다. ④ 결과 비교에서 확인하세요.")
        except Exception as exc:
            st.error(f"실험을 완료하지 못했습니다: {exc}")

with tab_result:
    result = st.session_state.get("result")
    if not result:
        st.write("③에서 실험을 실행하면 결과가 표시됩니다.")
    else:
        tables, meta = result
        st.caption("저장된 실행의 결과입니다. 현재 사이드바 설정과 다를 수 있습니다. 실행 당시 설정은 manifest에 있습니다.")
        if meta["failures"]:
            st.error(f"{meta['failures']}회 실패. 완전한 비교 블록만 정책 요약에 사용했습니다.")
        if "summary" in tables:
            st.subheader("두 장기 성과를 함께 봅니다")
            for measure, label in [("profit_per_budget", "약정예산당 누적 영업이익"), ("sustained_profit", "연속 2년 흑자 달성 기업 수")]:
                frame = tables["summary"][tables["summary"].metric.eq(measure)]
                chart = alt.Chart(frame).mark_bar().encode(x=alt.X("policy:N", sort=None, title="정책"),
                    y=alt.Y("mean:Q", title=label), color="world:N", xOffset="world:N",
                    tooltip=["world", "parameter_set", "policy", "mean", "mcse"]).facet(column="parameter_set:N")
                st.altair_chart(chart, use_container_width=True)
            st.caption("MCSE는 난수 반복에 따른 계산 오차입니다. 자료·모수·구조 불확실성을 포함하지 않습니다.")
            st.markdown("#### fixed와의 짝지은 차이")
            st.dataframe(tables["paired"], hide_index=True, use_container_width=True)
            st.markdown("#### 조건별 최대 후회와 Pareto 비교")
            st.dataframe(tables["robust"], hide_index=True, use_container_width=True)
            st.caption("시나리오별 Pareto 비중은 실제 세계의 발생 확률이 아닙니다.")
        history = tables["history"].groupby(["world", "policy", "year"], as_index=False)[["hhi", "unknown"]].mean()
        history["series"] = history.world + " / " + history.policy
        line(history, "hhi:Q", "추천권 집중도 경로")
        st.download_button("표·명세·HTML 보고서 ZIP", export_zip(tables, meta), "tips_abm_results.zip", mime="application/zip")
        with st.expander("실행 명세"):
            st.json(meta)

with tab_docs:
    st.subheader("연구 명세와 실행 기록")
    st.write("27개 구조 세계 × 37개 정책 × 허용 모수 집합 × 독립 반복은 CLI에서 계획을 확인한 뒤 실행합니다.")
    st.code("python -m tips_abm run --config configs/research.json --family worlds --grid --repetitions 200\n# 계획 확인 후 --accepted results/calibration --execute 추가", language="bash")
    for name, title in [("ODD.md", "ODD"), ("RESEARCH_PROTOCOL.md", "E0–E7 연구 명세"),
                        ("REPORTING_CROSSWALK.md", "ODD+D / TRACE / STRESS"), ("CLOUD_DEPLOY.md", "Cloud 배포")]:
        path = Path(__file__).parent / "docs" / name
        if path.exists():
            with st.expander(title):
                st.markdown(path.read_text(encoding="utf-8"))
    st.caption("코드 구현과 실행 검증·논문 결과 확정은 별도 단계입니다. IMPLEMENTATION_STATUS.md에서 구분해 기록합니다.")
