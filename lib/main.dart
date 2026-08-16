import 'package:trademind_ai/app.dart';
import 'package:trademind_ai/core/bootstrap.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppBootstrap.initialize();
  runApp(const ProviderScope(child: TradeMindApp()));
}
