const requiredHash = /^[a-f0-9]{64}$/;

export function createModelBoundaryAdapter({
  invokeModel,
  promptHash,
  toolsHash,
  maxTurns = 8,
}) {
  if (typeof invokeModel !== "function") {
    throw new TypeError("invokeModel must be a function");
  }
  if (!requiredHash.test(promptHash) || !requiredHash.test(toolsHash)) {
    throw new TypeError("promptHash and toolsHash must be SHA-256 values");
  }

  return async function invokeAtFixedBoundary(request) {
    if (request.promptHash !== promptHash || request.toolsHash !== toolsHash) {
      throw new Error("Frozen model-boundary hash mismatch");
    }
    if (!Array.isArray(request.messages) || !Array.isArray(request.tools)) {
      throw new TypeError("messages and tools must be arrays");
    }
    if (request.turn > maxTurns) {
      throw new Error("Maximum model turns exceeded");
    }

    const response = await invokeModel({
      messages: structuredClone(request.messages),
      tools: structuredClone(request.tools),
      temperature: request.temperature ?? 0,
      stream: Boolean(request.stream),
    });

    return {
      content: response.content ?? null,
      toolCalls: Array.isArray(response.toolCalls) ? response.toolCalls : [],
      usage: response.usage ?? null,
      model: response.model ?? "candidate",
    };
  };
}
