const TRANSLATIONS = {
  en: {
    tagline: "Ask anything about The Webb Schools",
    placeholder: "Ask a question...",
    welcome: "Hi! I'm the Webb AI Assistant. I can answer questions about campus life, academics, clubs, admissions, and more. How can I help you?",
    sources: "Sources:",
    error: "Sorry, something went wrong. Please try again.",
    rateLimit: "Too many requests. Please wait a moment.",
  },
  zh: {
    tagline: "关于 Webb Schools 的一切问题，我来解答",
    placeholder: "请输入您的问题...",
    welcome: "您好！我是 Webb AI 助手。我可以回答关于校园生活、学术课程、社团、招生等方面的问题。请问有什么可以帮到您？",
    sources: "来源：",
    error: "抱歉，出了点问题，请稍后再试。",
    rateLimit: "请求过于频繁，请稍等片刻。",
  },
  es: {
    tagline: "Pregunta cualquier cosa sobre The Webb Schools",
    placeholder: "Escribe tu pregunta...",
    welcome: "¡Hola! Soy el asistente de IA de Webb. Puedo responder preguntas sobre la vida en el campus, académicos, clubes, admisiones y más. ¿En qué puedo ayudarte?",
    sources: "Fuentes:",
    error: "Lo sentimos, algo salió mal. Por favor intenta de nuevo.",
    rateLimit: "Demasiadas solicitudes. Por favor espera un momento.",
  },
  ko: {
    tagline: "Webb Schools에 관한 모든 것을 물어보세요",
    placeholder: "질문을 입력하세요...",
    welcome: "안녕하세요! Webb AI 어시스턴트입니다. 캠퍼스 생활, 학업, 동아리, 입학 등에 관한 질문에 답해드릴 수 있습니다. 무엇을 도와드릴까요?",
    sources: "출처:",
    error: "죄송합니다, 오류가 발생했습니다. 다시 시도해 주세요.",
    rateLimit: "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
  },
  ja: {
    tagline: "Webb Schoolsについて何でも聞いてください",
    placeholder: "質問を入力してください...",
    welcome: "こんにちは！Webb AIアシスタントです。キャンパスライフ、学習、クラブ活動、入学などについてお答えします。何かご質問はありますか？",
    sources: "出典：",
    error: "申し訳ありません、エラーが発生しました。もう一度お試しください。",
    rateLimit: "リクエストが多すぎます。しばらくお待ちください。",
  },
  vi: {
    tagline: "Hỏi bất cứ điều gì về The Webb Schools",
    placeholder: "Nhập câu hỏi của bạn...",
    welcome: "Xin chào! Tôi là trợ lý AI của Webb. Tôi có thể trả lời các câu hỏi về đời sống ký túc xá, học tập, câu lạc bộ, tuyển sinh và nhiều hơn nữa. Tôi có thể giúp gì cho bạn?",
    sources: "Nguồn:",
    error: "Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.",
    rateLimit: "Quá nhiều yêu cầu. Vui lòng đợi một chút.",
  },
  th: {
    tagline: "ถามอะไรก็ได้เกี่ยวกับ The Webb Schools",
    placeholder: "พิมพ์คำถามของคุณ...",
    welcome: "สวัสดีค่ะ! ฉันคือผู้ช่วย AI ของ Webb ฉันสามารถตอบคำถามเกี่ยวกับชีวิตในโรงเรียน การเรียน ชมรม การรับสมัคร และอื่นๆ มีอะไรให้ช่วยไหมคะ?",
    sources: "แหล่งที่มา:",
    error: "ขออภัย เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง",
    rateLimit: "คำขอมากเกินไป กรุณารอสักครู่",
  },
};

let currentLang = "en";
let chatHistory = [];
let isLoading = false;

// Configure marked for safe rendering
marked.setOptions({
  breaks: true,       // Convert \n to <br>
  gfm: true,          // GitHub Flavored Markdown
});

function t(key) {
  return TRANSLATIONS[currentLang]?.[key] || TRANSLATIONS.en[key];
}

function renderMarkdown(text) {
  return marked.parse(text);
}

function setLanguage(lang) {
  currentLang = lang;
  document.getElementById("tagline").textContent = t("tagline");
  document.getElementById("input").placeholder = t("placeholder");
  document.getElementById("welcome-msg").querySelector(".bubble").textContent = t("welcome");
}

document.getElementById("lang-select").addEventListener("change", (e) => {
  setLanguage(e.target.value);
});

function appendMessage(role, content, sources = []) {
  const chatWindow = document.getElementById("chat-window");
  const div = document.createElement("div");
  div.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  if (role === "user") {
    // User messages: plain text (safe, no injection)
    bubble.textContent = content;
  } else {
    // Assistant messages: render markdown
    bubble.innerHTML = renderMarkdown(content);
  }
  div.appendChild(bubble);

  appendSources(div, sources);

  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

function appendSources(messageDiv, sources) {
  if (sources.length > 0) {
    messageDiv.querySelector(".sources")?.remove();
    const src = document.createElement("div");
    src.className = "sources";
    src.textContent = t("sources") + " ";
    sources.forEach((name, i) => {
      const span = document.createElement("span");
      span.className = "source-tag";
      if (name.startsWith("http")) {
        const a = document.createElement("a");
        a.href = name;
        a.target = "_blank";
        a.textContent = `[${i + 1}]`;
        span.appendChild(a);
      } else {
        span.textContent = name;
      }
      if (i > 0) src.appendChild(document.createTextNode(", "));
      src.appendChild(span);
    });
    messageDiv.appendChild(src);
  }
}

// Create an empty assistant message bubble for streaming
function appendStreamingMessage() {
  const chatWindow = document.getElementById("chat-window");
  const div = document.createElement("div");
  div.className = "message assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = "";
  div.appendChild(bubble);

  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return div;
}

function showTyping() {
  const chatWindow = document.getElementById("chat-window");
  const div = document.createElement("div");
  div.className = "message assistant typing";
  div.id = "typing-indicator";
  div.innerHTML = `<div class="bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>`;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function hideTyping() {
  document.getElementById("typing-indicator")?.remove();
}

async function sendMessage() {
  if (isLoading) return;

  const input = document.getElementById("input");
  const question = input.value.trim();
  if (!question) return;

  input.value = "";
  input.style.height = "auto";
  isLoading = true;
  document.getElementById("send-btn").disabled = true;

  appendMessage("user", question);
  chatHistory.push({ role: "user", content: question });
  showTyping();

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history: chatHistory.slice(-6) }),
    });

    hideTyping();

    if (response.status === 429) {
      appendMessage("assistant", t("rateLimit"));
      return;
    } else if (!response.ok) {
      appendMessage("assistant", t("error"));
      return;
    }

    // Create empty bubble for streaming
    const msgDiv = appendStreamingMessage();
    const bubble = msgDiv.querySelector(".bubble");
    let fullText = "";
    let sources = [];

    // Throttle markdown rendering during streaming (every 100ms)
    let renderTimer = null;
    function scheduleRender() {
      if (!renderTimer) {
        renderTimer = setTimeout(() => {
          bubble.innerHTML = renderMarkdown(fullText);
          const chatWindow = document.getElementById("chat-window");
          chatWindow.scrollTop = chatWindow.scrollHeight;
          renderTimer = null;
        }, 100);
      }
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.slice(6);
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);

          if (event.type === "sources") {
            sources = event.sources;
          } else if (event.type === "delta") {
            fullText += event.text;
            scheduleRender();
          } else if (event.type === "done") {
            // Final render with markdown
            if (renderTimer) {
              clearTimeout(renderTimer);
              renderTimer = null;
            }
            bubble.innerHTML = renderMarkdown(fullText);
            appendSources(msgDiv, sources);
            const chatWindow = document.getElementById("chat-window");
            chatWindow.scrollTop = chatWindow.scrollHeight;
          } else if (event.type === "error") {
            bubble.textContent = t("error");
          }
        } catch (e) {
          // skip malformed JSON
        }
      }
    }

    // Safety: if stream ends without "done" event, render final state
    if (renderTimer) {
      clearTimeout(renderTimer);
    }
    bubble.innerHTML = renderMarkdown(fullText);
    if (sources.length > 0 && !msgDiv.querySelector(".sources")) {
      appendSources(msgDiv, sources);
    }

    chatHistory.push({ role: "assistant", content: fullText });
  } catch (err) {
    hideTyping();
    appendMessage("assistant", t("error"));
  } finally {
    isLoading = false;
    document.getElementById("send-btn").disabled = false;
    input.focus();
  }
}

// Auto-resize textarea
document.getElementById("input").addEventListener("input", function () {
  this.style.height = "auto";
  this.style.height = Math.min(this.scrollHeight, 120) + "px";
});

// Send on Enter (Shift+Enter for newline)
document.getElementById("input").addEventListener("keydown", function (e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
