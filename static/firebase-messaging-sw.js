// firebase-messaging-sw.js

importScripts("https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js");

const firebaseConfig = {
    apiKey: "AIzaSyDkL_xTKrpe8CdDQivEd_p5IJI48PF_ebs",
    authDomain: "miniplex-1620d.firebaseapp.com",
    projectId: "miniplex-1620d",
    messagingSenderId: "872713172733",
    appId: "1:872713172733:web:8a22463991ca4b5a6a3094"
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
