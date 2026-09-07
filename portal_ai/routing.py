from .client import InternalApiError, InternalChatClient


AUTHOR_CHOICES = ("luna", "terra", "sol")

ROUTING_PROMPT = """추가 필수 출력 필드: author_choice, routing_basis.
author_choice는 luna, terra, sol 중 하나만 반환한다. routing_basis는 필요한 작업을 설명하는 짧은 한 문장이다. 규정의 결론이나 사고 과정을 적지 않는다.
질문과 이전 대화 맥락에서 답변에 필요한 판단의 성격으로 선택한다.
luna: 용어 설명, 명명된 항목 찾기, 파일/사진 제공처럼 업무상 허용 여부나 의무를 판단하지 않는 요청. 단순 인사나 확인 질문도 포함한다.
terra: 대상이 이미 정해진 일반 규정의 기준·요건·절차·선택지를 조건과 함께 설명하는 요청. 단순 규정 조회는 luna가 아니라 terra이다.
sol: 사용자 상황에 어떤 작업/장소/역할 분류나 규정이 적용되는지 먼저 판단하거나, 일반 의무와 예외를 구분하거나, 상호작용하는 범위·조건을 종합해야 하는 요청.
숫자·약어·조건 개수·허용 여부를 묻는 말투·예상 답변 길이만으로 복잡도를 결정하지 않는다.
파일이나 사진 요청에 업무상 판단이 포함되면 파일 제공 자체가 아니라 그 판단을 기준으로 선택한다.
luna/terra 사이에서 애매하면 terra, terra/sol 사이에서 애매하면 sol을 선택한다. 일정 사용 비율을 맞추려 하지 않는다.
아직 검색 결과를 보지 않았으므로 이 선택은 예상 작업량 분류일 뿐 근거의 충분성이나 답변 정확성을 보증하지 않는다."""


class ModelRouting:
    def __init__(self, config):
        self.enabled = config.getboolean("AI_MODEL_ROUTING", "enabled", fallback=False)
        if self.enabled:
            models = {choice: config.get("AI_MODEL_ROUTING", choice + "_model", fallback="").strip()
                      for choice in AUTHOR_CHOICES}
            missing = [choice + "_model" for choice, model in models.items() if not model]
            if missing:
                raise InternalApiError("[AI_MODEL_ROUTING] 모델명을 입력해 주세요: " + ", ".join(missing))
            self.clients = {choice: InternalChatClient(config, model_name=model) for choice, model in models.items()}
        else:
            self.clients = {"luna": InternalChatClient(config)}
        self.semantic_client = self.clients["luna"]

    def answer_client(self, choice):
        if choice not in AUTHOR_CHOICES:
            raise InternalApiError("허용되지 않은 답변 모델 역할입니다.")
        return self.clients[choice] if self.enabled else self.semantic_client

    def metadata(self, choice=None, basis=""):
        return {
            "model_routing": self.enabled,
            "semantic_model": self.semantic_client.model,
            "answer_model": self.answer_client(choice).model if choice is not None else "",
            "author_choice": choice if self.enabled and choice is not None else "",
            "routing_basis": basis if self.enabled else "",
        }
