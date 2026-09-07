from portal_ai.pipeline import answer_events


def ask_internal_ai(question, context=None):
    chunks = []
    result = {}
    for event in answer_events(question, context):
        if event["event"] == "chunk":
            chunks.append(event["text"])
        elif event["event"] == "meta":
            result.update({key: value for key, value in event.items() if key != "event"})
    result["answer"] = "".join(chunks)
    return result


def ask_internal_ai_stream(question, context=None):
    yield from answer_events(question, context)
