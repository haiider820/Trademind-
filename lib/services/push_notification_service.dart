import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

class PushNotificationService {
  Future<bool> initialize() async {
    try {
      await Firebase.initializeApp();
      final messaging = FirebaseMessaging.instance;
      await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<String?> getToken() async {
    try {
      return FirebaseMessaging.instance.getToken();
    } catch (_) {
      return null;
    }
  }

  String platformName() {
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'ios';
    return 'web';
  }
}
