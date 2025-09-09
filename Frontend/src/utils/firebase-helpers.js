import { db } from "../lib/firebase"
import { collection, addDoc, query, where, orderBy, getDocs, doc, deleteDoc, serverTimestamp } from "firebase/firestore"

export async function saveSearchHistory(userId, searchTerm, resultCount) {
  try {
    const userRef = doc(db, "users", userId);
    const searchesCol = collection(userRef, "searches");
    
    await addDoc(searchesCol, {
      query: searchTerm,
      resultCount: resultCount,
      timestamp: serverTimestamp()
    });
    
    console.log("Search history saved successfully");
  } catch (error) {
    console.error("Error saving search history:", error);
    throw error;
  }
}

// Get user's search history
export async function getSearchHistory(userId) {
  try {
    const userRef = doc(db, "users", userId)
    const searchesCol = collection(userRef, "searches")
    const q = query(searchesCol, orderBy("timestamp", "desc"))

    const querySnapshot = await getDocs(q)
    return querySnapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }))
  } catch (error) {
    console.error("Error getting search history:", error)
    throw error
  }
}

// Delete a specific history item
export async function deleteSearchHistoryItem(userId, historyId) {
  try {
    const searchDocRef = doc(db, "users", userId, "searches", historyId)
    await deleteDoc(searchDocRef)
  } catch (error) {
    console.error("Error deleting history item:", error)
    throw error
  }
}

// Clear all search history for a user
export async function clearSearchHistory(userId) {
  try {
    const userRef = doc(db, "users", userId)
    const searchesCol = collection(userRef, "searches")
    const q = query(searchesCol)
    const querySnapshot = await getDocs(q)

    const deletePromises = querySnapshot.docs.map((doc) => deleteDoc(doc.ref))
    await Promise.all(deletePromises)
  } catch (error) {
    console.error("Error clearing search history:", error)
    throw error
  }
}

// Save chat message
export async function saveChatMessage(userId, caseId, message) {
  try {
    await addDoc(collection(db, "chatHistory"), {
      userId,
      caseId,
      message: message.text,
      response: message.response,
      timestamp: serverTimestamp(),
    })
  } catch (error) {
    console.error("Error saving chat message:", error)
    throw error
  }
}

// Get chat history for a specific case
export async function getChatHistory(userId, caseId) {
  try {
    const chatRef = collection(db, "chatHistory")
    const q = query(chatRef, where("userId", "==", userId), where("caseId", "==", caseId), orderBy("timestamp", "asc"))

    const querySnapshot = await getDocs(q)
    return querySnapshot.docs.map((doc) => ({
      id: doc.id,
      ...doc.data(),
    }))
  } catch (error) {
    console.error("Error getting chat history:", error)
    throw error
  }
}
