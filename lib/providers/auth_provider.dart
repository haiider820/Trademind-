import 'package:trademind_ai/services/auth_service.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final authServiceProvider = Provider<AuthService>((ref) => AuthService());

final authStateProvider = StreamProvider<Session?>((ref) {
  final service = ref.watch(authServiceProvider);
  final session = service.currentSession;
  final stream = service.authStateChanges().map((event) => event.session);
  return Stream<Session?>.multi((controller) {
    controller.add(session);
    final sub = stream.listen(
      controller.add,
      onError: controller.addError,
      onDone: controller.close,
    );
    controller.onCancel = sub.cancel;
  });
});
