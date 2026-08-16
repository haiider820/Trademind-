import 'package:flutter/foundation.dart';
import 'package:trademind_ai/core/config/supabase_env.dart';

class AppConfig {
  static String get apiBaseUrl {
    final definedBaseUrl = const String.fromEnvironment('API_BASE_URL', defaultValue: '');
    if (definedBaseUrl.isNotEmpty) {
      return definedBaseUrl;
    }
    if (kIsWeb) {
      return 'http://localhost:8000/api/v1';
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        if (kDebugMode) {
          return 'http://192.168.100.110:8000/api/v1';
        }
        throw StateError('API_BASE_URL must be provided with --dart-define for Android release builds');
      case TargetPlatform.iOS:
      case TargetPlatform.macOS:
      case TargetPlatform.windows:
      case TargetPlatform.linux:
        if (kDebugMode) {
          return 'http://localhost:8000/api/v1';
        }
        throw StateError('API_BASE_URL must be provided with --dart-define for non-web release builds');
      case TargetPlatform.fuchsia:
        if (kDebugMode) {
          return 'http://localhost:8000/api/v1';
        }
        throw StateError('API_BASE_URL must be provided with --dart-define');
    }
  }

  static String get supabaseUrl =>
      const String.fromEnvironment('SUPABASE_URL', defaultValue: defaultSupabaseUrl);

  static String get supabaseAnonKey =>
      const String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: defaultSupabaseAnonKey);

  static bool get supabaseConfigured => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;
}
