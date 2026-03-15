# etlers_portal

이틀러스 웹 메인 포탈입니다. `etlers.com`과 `www.etlers.com`은 포탈을 보여주고,
`ekis.etlers.com`은 기존 EKIS 로그인 화면으로, `forcast.etlers.com`은 ETF
Forecast 서비스로 프록시되도록 구성합니다. 앞단 게이트웨이는 `Caddy`를 사용하므로
HTTPS 인증서 발급과 갱신을 자동으로 처리합니다.

## 구조

- `gateway`: 외부 `80`, `443` 포트를 받는 Caddy reverse proxy
- `portal`: 포탈 메인 화면을 서빙하는 nginx
- `contact-api`: 포탈의 슬랙 문의를 처리하는 경량 API
- `ekis`: 기존 운영 중인 컨테이너. 이 저장소에서는 직접 띄우지 않고 프록시 대상으로 연결
- `forecast`: 호스트 `6104` 포트에서 실행 중인 ETF Forecast 서비스. 이 저장소에서는 직접 띄우지 않고 프록시 대상으로 연결

## 포트 구성 원칙

기존에는 EKIS가 호스트 `80` 포트를 직접 사용했더라도, 이제는 `gateway`가 호스트
`80`, `443` 포트를 가져가야 합니다.

즉, 운영 형태는 아래처럼 바뀝니다.

- 변경 전: `host:80 -> ekis:80`
- 변경 후: `host:80/443 -> gateway -> portal / ekis / forecast / contact-api`

EKIS 컨테이너 내부 포트가 `80`인 것은 문제 없습니다. 다만 호스트 포트 바인딩은
다른 포트로 옮겨야 합니다.

예시:

- EKIS 컨테이너: `8080:80`
- 포탈 게이트웨이: `80:80`, `443:443`

## 빠른 적용 절차

1. 기존 EKIS 웹 컨테이너의 호스트 포트 바인딩을 `80:80`에서 `8080:80`으로 변경합니다.
2. DNS에서 아래 도메인이 현재 서버의 공인 IP를 가리키도록 설정합니다.
   - `etlers.com`
   - `www.etlers.com`
   - `ekis.etlers.com`
   - `forcast.etlers.com`
3. `.env.example`을 참고해 필요하면 `.env`를 생성합니다.
4. 슬랙 DM 문의 기능을 사용할 경우 `env/slack_info.json`에 관리자 `slack_id`와 `SLACK_USER_TOKEN`을 넣습니다.
5. 이 저장소에서 아래 명령으로 포탈 스택을 띄웁니다.

```bash
docker compose up -d --build
```

기본값 기준으로 gateway는 아래 업스트림을 프록시합니다.

- `ekis.etlers.com -> host.docker.internal:8080`
- `forcast.etlers.com -> host.docker.internal:6104`

즉, Mac Docker 환경에서 기존 EKIS가 호스트 `8080`, Forecast 서비스가 호스트 `6104`에
publish 되어 있으면 바로 붙습니다.

DNS가 이미 반영되어 있고 방화벽에서 `80`, `443`이 열려 있으면 Caddy가
`etlers.com`, `www.etlers.com`, `ekis.etlers.com`, `forcast.etlers.com`에 대해
자동으로 인증서를 발급하고 HTTPS를 활성화합니다.

## 포탈 기능

- `EKIS` 카드: EKIS 로그인 화면으로 이동
- `Forcast` 카드: 인공지능으로 분석한 ETF Forecast 서비스 화면으로 이동
- `관리자에게 문의`: 이메일 문의와 슬랙 DM 문의 제공

슬랙 DM 문의는 포탈 화면에서 모달 입력창을 띄운 뒤 `/api/contact/slack` API를 호출해
`env/slack_info.json`에 설정한 관리자 계정으로 DM을 전송합니다. 슬랙 토큰은
브라우저로 노출되지 않고 `contact-api` 컨테이너에서만 읽습니다.

## 환경 변수

- `ACME_EMAIL`: HTTPS 인증서 발급 알림용 이메일
- `EKIS_UPSTREAM_HOST`: 게이트웨이가 프록시할 EKIS 대상 호스트
- `EKIS_UPSTREAM_PORT`: 게이트웨이가 프록시할 EKIS 대상 포트
- `FORECAST_UPSTREAM_HOST`: 게이트웨이가 프록시할 Forecast 대상 호스트
- `FORECAST_UPSTREAM_PORT`: 게이트웨이가 프록시할 Forecast 대상 포트

## 슬랙 문의 설정

`env/slack_info.json` 예시:

```json
{
  "slack_id": "UXXXXXXXXXX",
  "SLACK_USER_TOKEN": "xoxp-..."
}
```

- `slack_id`: DM을 받을 관리자 Slack 사용자 ID
- `SLACK_USER_TOKEN`: `conversations.open`, `chat.postMessage` 호출이 가능한 사용자 토큰

토큰은 민감 정보이므로 저장소 공개 범위와 배포 환경 권한을 함께 확인하는 것이 좋습니다.

## 참고

만약 EKIS를 `etlers.com/ekis` 같은 서브패스로 붙이고 싶다면 EKIS 애플리케이션이
서브패스를 인식하도록 별도 수정이 필요할 수 있습니다. 현재 구성은 그 리스크를 줄이기
위해 `ekis.etlers.com` 서브도메인 방식을 기준으로 작성했습니다.
