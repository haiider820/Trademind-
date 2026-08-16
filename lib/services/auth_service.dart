import 'package:trademind_ai/core/config/app_config.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class AuthService {
  Stream<AuthState> authStateChanges() {
    if (!AppConfig.supabaseConfigured) {
      return const Stream<AuthState>.empty();
    }
    return Supabase.instance.client.auth.onAuthStateChange;
  }

  Session? get currentSession {
    if (!AppConfig.supabaseConfigured) {
      return null;
    }
    return Supabase.instance.client.auth.currentSession;
  }

  Future<void> signIn({
    required String email,
    required String password,
  }) async {
    if (!AppConfig.supabaseConfigured) {
      throw Exception('Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY.');
    }

    await Supabase.instance.client.auth.signInWithPassword(
      email: email,
      password: password,
    );
  }

  Future<void> signUp({
    required String email,
    required String password,
  }) async {
    if (!AppConfig.supabaseConfigured) {
      throw Exception('Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY.');
    }

    await Supabase.instance.client.auth.signUp(
      email: email,
      password: password,
    );
  }

  Future<void> signOut() async {
    if (!AppConfig.supabaseConfigured) {
      return;
    }
    await Supabase.instance.client.auth.signOut();
  }
}
