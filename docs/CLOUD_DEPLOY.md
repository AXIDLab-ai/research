# Streamlit Community Cloud 배포

## 저장소 구조

권장: `tips_simulator` 폴더의 **내용**을 새 GitHub 저장소의 최상위에 둔다. 업로드용 ZIP도 이 구조다.

```text
app.py
requirements.txt
pyproject.toml
.streamlit/config.toml
tips_abm/
configs/
docs/
scripts/
README.md
```

`data_private`, `results`, `.venv`, Excel, pickle, secrets는 배포 파일에 포함하지 않는다. 코드의 공개 라이선스와 저자 표기는 저장소 소유자가 결정해야 한다. 공개 GitHub 저장소에 올리는 것만으로 특정 오픈소스 라이선스를 부여하지 않는다.

## 배포 단계

1. GitHub에 새 저장소를 만들고 배포 ZIP의 내용을 저장소 최상위에 올린다. 숨김 폴더 `.streamlit`도 포함한다.
2. [Streamlit Community Cloud](https://share.streamlit.io/)에서 Create app을 선택한다.
3. 저장소·브랜치를 선택하고 Main file path를 **app.py**로 지정한다.
4. Advanced settings에서 Python **3.12**를 선택한다. dependencies는 루트 requirements.txt를 사용한다.
5. Deploy를 누른다. 최초 화면은 합성자료 모드이며 시뮬레이션은 버튼을 눌러야 시작한다.

상위 연구 폴더 전체를 저장소에 올리는 방식은 권하지 않는다. 꼭 하위 폴더로 둘 경우 entrypoint와 의존성 탐색 규칙을 맞춰야 하며 이 패키지는 루트 배치를 기준으로 제공한다.

공식 문서: [배포](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [파일 구성](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization), [의존성](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies), [앱 관리](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).

## 실제 자료 업로드: 선택 기능

공개 기본값은 업로드 비활성화다. 연구자료를 해당 서버에서 처리할 수 있고 앱 접근 범위를 정한 후 App settings → Secrets에 다음을 넣으면 업로드 UI가 열린다.

```toml
ENABLE_PRIVATE_UPLOAD = true
```

이 값은 사용자 인증 기능이 아니다. 앱의 접근 통제는 배포자가 별도로 설정한다. Excel 업로드 시 자료가 Streamlit 서버로 전송된다. 앱 코드는 원본 파일을 디스크에 저장하지 않고 메모리에서 읽으며, 실제 Bundle은 사용자 session_state에만 둔다. 합성 Bundle만 공유 캐시를 사용한다. 업로드 데이터가 GitHub에 커밋되지는 않는다. 서비스 자체의 인프라·로그·보존 정책까지 이 코드가 통제하지는 않는다.

업로드 한도는 앱 설정에서 50MB로 정했다. 대형 원자료·민감자료는 로컬 CLI로 처리하고 공개 앱에는 합성 모드만 유지할 수 있다. 배포된 서버의 임시 파일에 연구결과를 장기 보관하지 말고 결과 ZIP을 내려받는다.

## 자원 관리

- 화면 실험 한도는 120회와 추정 기업-연도 2,000,000이다. 서비스 전체의 공식 자원 한도를 의미하지 않는다.
- 보정 화면은 후보 4–16개, 후보당 2회로 제한한다. 이 작은 계산만으로 논문용 보정을 확정하지 않는다.
- 27세계×37정책×모수집합×200회 이상은 로컬/연구서버 CLI에서 실행한다.
- 공개 화면은 자동 배치·백그라운드 작업을 시작하지 않는다. 실행 중 새 브라우저 세션이 같은 private 입력을 공유하지 않는다.
- 무료 호스팅의 사용량·리소스·슬립 정책은 바뀔 수 있으므로 실제 배포 시 공식 관리 문서를 확인한다.

## 장애 시 확인

Python 3.12, entrypoint app.py, requirements.txt 위치를 먼저 확인한다. 앱 로그에서 dependency 오류를 확인한다. 새 코드를 올렸는데 이전 화면이면 배포한 브랜치·커밋을 확인한다. 원자료 레이아웃이 달라지면 자동으로 추측하지 말고 data.prepare_excel의 열 사전을 수정하고 새로운 입력 해시로 다시 보정한다.
