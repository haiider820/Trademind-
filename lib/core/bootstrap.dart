import 'package:trademind_ai/core/config/app_config.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:trademind_ai/firebase_options.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class AppBootstrap {
  static Future<void> initialize() async {
    await Hive.initFlutter();
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
    if (AppConfig.supabaseConfigured) {
      await Supabase.initialize(
        url: AppConfig.supabaseUrl,
        anonKey: AppConfig.supabaseAnonKey,
      );
    }
  }
}
