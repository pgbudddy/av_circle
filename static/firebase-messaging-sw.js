// firebase-messaging-sw.js

importScripts("https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js");

const firebaseConfig = {
    apiKey: "AIzaSyCn9U9xtcEHLnULN71X2nN-SUcd3WDN6GE",
    authDomain: "miniplex-66f40.firebaseapp.com",
    projectId: "miniplex-66f40",      
    messagingSenderId: "100301976368",
    appId: "1:100301976368:web:2185594b8c6f38834c8ef5",
  };

firebase.initializeApp(firebaseConfig);

const messaging = firebase.messaging();

// Optional: Background message handler
messaging.onBackgroundMessage((payload) => {
  console.log('[firebase-messaging-sw.js] Received background message ', payload);

  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/static/images/logo3.png'  // or any fallback icon
  };

  self.registration.showNotification(notificationTitle, notificationOptions);
});
