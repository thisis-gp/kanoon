const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const defaultOptions = {
    headers: {
      "Content-Type": "application/json",
    },
  };

  try {
    const response = await fetch(url, { ...defaultOptions, ...options });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || "API request failed");
    }
    
    return await response.json();
  } catch (error) {
    console.error("API Error:", error);
    throw error;
  }
}

// Search API
export async function searchLegalCases(query, topK = 5) {
  try {
    const response = await fetchAPI("/query", {
      method: "POST",
      body: JSON.stringify({
        query: query,
        top_k: topK
      }),
    });

    return response.results.map(result => ({
      id: result.id,
      title: result.title,
      judges: result.judges,
      date: result.date,
      summary: result.summary,
      source: result.source
    }));
  } catch (error) {
    console.error("Search error:", error);
    throw error;
  }
}

// Case Metadata API
export async function getCaseMetadata(source) {
  return fetchAPI("/structured_query", {
    method: "POST",
    body: JSON.stringify({
      text: "", // Text can be empty if using cached data
      source: source
    }),
  });
}

// Document Management API
export async function uploadLegalDocuments(filePath) {
  return fetchAPI("/add-documents", {
    method: "POST",
    body: JSON.stringify({ file_path: filePath }),
  });
}

// Chat API
export async function initializeCaseChat(caseId) {
  return fetchAPI("/chat_init", {
    method: "POST",
    body: JSON.stringify({ case_id: caseId }),
  });
}

export async function sendChatMessage(caseId, question) {
  return fetchAPI(`/chat_query`, {
    method: "POST",
    body: JSON.stringify({
      case_id: caseId,
      question: question
    }),
  });
}

// Text-to-Speech API
export async function textToSpeech(text) {
  // This would be implemented on your backend
  // For now, we'll create a simple endpoint that would use gTTS
  return fetchAPI("/text-to-speech", {
    method: "POST",
    body: JSON.stringify({ text }),
  })
}

// Additional Helper Functions
export async function getFullCaseDetails(source) {
  const metadata = await getCaseMetadata(source);
  
  return {
    ...metadata.data,
    pdfUrl: `/documents/${source}.pdf`, // Example PDF URL pattern
    relatedCases: await searchLegalCases(metadata.data.title, 3)
  };
}

 // Update getCaseById function
export async function getCaseById(id) {
    const response = await fetchAPI(`/cases/${id}`);
    console.log("Case API response:", response)
    const result = {
      ...response,
      pdfUrl: `/supreme_court_pdfs/${id}.pdf`,
      summaryUrl: `/supreme_court_pdfs/${id}.pdf` // Using PDF as summary for now
    };
    console.log("Final case data with PDF URL:", result)
    return result;
}