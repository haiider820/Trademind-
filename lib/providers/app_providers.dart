import 'package:trademind_ai/core/network/api_client.dart';
import 'package:trademind_ai/models/market_candle.dart';
import 'package:trademind_ai/models/market_overview.dart';
import 'package:trademind_ai/models/news_item.dart';
import 'package:trademind_ai/models/trade_signal.dart';
import 'package:trademind_ai/services/device_service.dart';
import 'package:trademind_ai/services/push_notification_service.dart';
import 'package:trademind_ai/services/trademind_api_service.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final tradeMindApiServiceProvider = Provider<TrademindApiService>(
  (ref) => TrademindApiService(apiClient: ref.read(apiClientProvider)),
);

final pushNotificationServiceProvider = Provider<PushNotificationService>(
  (ref) => PushNotificationService(),
);

final deviceServiceProvider = Provider<DeviceService>(
  (ref) => DeviceService(ref.read(apiClientProvider)),
);

final marketOverviewProvider = FutureProvider<MarketOverview>((ref) async {
  return ref.read(tradeMindApiServiceProvider).getMarketOverview();
});

final newsProvider = FutureProvider<List<NewsItem>>((ref) async {
  final items = await ref.read(tradeMindApiServiceProvider).getNews();
  return items.map((e) => NewsItem.fromJson(e as Map<String, dynamic>)).toList();
});

final signalsProvider = FutureProvider<List<TradeSignal>>((ref) async {
  final items = await ref.read(tradeMindApiServiceProvider).getSignals();
  return items.map((e) => TradeSignal.fromJson(e as Map<String, dynamic>)).toList();
});

final marketSummaryProvider = FutureProvider<List<MarketSummaryItem>>((ref) async {
  return ref.read(tradeMindApiServiceProvider).getMarketSummary();
});

final candlesProvider = FutureProvider.family<List<MarketCandle>, ({String symbol, String interval})>((ref, request) async {
  return ref.read(tradeMindApiServiceProvider).getCandles(
        symbol: request.symbol,
        interval: request.interval,
        limit: 120,
      );
});

final currentUserRoleProvider = FutureProvider<String?>((ref) async {
  final user = Supabase.instance.client.auth.currentUser;
  if (user == null) {
    return null;
  }

  final row = await Supabase.instance.client
      .from('profiles')
      .select('role')
      .eq('id', user.id)
      .maybeSingle();

  if (row == null) {
    return null;
  }

  return row['role'] as String?;
});

final currentUserProfileProvider = FutureProvider<Map<String, dynamic>?>((ref) async {
  final user = Supabase.instance.client.auth.currentUser;
  if (user == null) {
    return null;
  }

  final row = await Supabase.instance.client
      .from('profiles')
      .select('role, subscription, name')
      .eq('id', user.id)
      .maybeSingle();

  if (row == null) {
    return null;
  }

  return Map<String, dynamic>.from(row as Map);
});
