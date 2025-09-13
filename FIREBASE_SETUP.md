# Firebase Setup Guide

## Required Firestore Index

The chat history feature requires a Firestore index. Please create the following index:

### Index Details:
- **Collection**: `chat_history`
- **Fields**: 
  - `caseId` (Ascending)
  - `userId` (Ascending) 
  - `timestamp` (Descending)
  - `__name__` (Ascending)

### How to Create:
1. Go to [Firebase Console](https://console.firebase.google.com/v1/r/project/kanoon-f2a0f/firestore/indexes)
2. Click "Create Index"
3. Add the fields in the order specified above
4. Set the sort order as indicated
5. Click "Create"

### Alternative:
You can also click the link provided in the error message to create the index automatically.

## Environment Variables

Make sure these are set in your Vercel environment:
- `VITE_FIREBASE_API_KEY`
- `VITE_FIREBASE_AUTH_DOMAIN`
- `VITE_FIREBASE_PROJECT_ID`
- `VITE_FIREBASE_STORAGE_BUCKET`
- `VITE_FIREBASE_MESSAGING_SENDER_ID`
- `VITE_FIREBASE_APP_ID`
