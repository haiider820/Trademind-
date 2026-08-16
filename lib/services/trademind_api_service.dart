import 'package:trademind_ai/core/network/api_client.dart';
import 'package:trademind_ai/models/market_candle.dart';
import 'package:trademind_ai/models/market_overview.dart';

class TrademindApiService {
  TrademindApiService({ApiClient? apiClient}) : _apiClient = apiClient ?? ApiClient();

  final ApiClient _apiClient;

  Future<MarketOverview> getMarketOverview() async {
    final response = await _apiClient.get('/market/overview');
    final data = Map<String, dynamic>.from(response.data as Map);
    return MarketOverview.fromJson(data);
  }

  Future<List<MarketSummaryItem>> getMarketSummary() async {
    final response = await _apiClient.get('/market/summary');
    final data = Map<String, dynamic>.from(response.data as Map);
    final items = (data['items'] as List<dynamic>? ?? const []);
    return items
        .map((item) => MarketSummaryItem.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }

  Future<List<Map<String, dynamic>>> getAllCryptoPrices({String quoteAsset = 'USDT'}) async {
    final response = await _apiClient.get(
      '/market/all',
      queryParameters: {'quote_asset': quoteAsset},
    );
    final data = Map<String, dynamic>.from(response.data as Map);
    final items = (data['items'] as List<dynamic>? ?? const []);
    return items.map((item) => Map<String, dynamic>.from(item as Map)).toList();
  }

  Future<List<MarketCandle>> getCandles({
    required String symbol,
    required String interval,
    int limit = 100,
  }) async {
    final response = await _apiClient.get(
      '/market/candles',
      queryParameters: {
        'symbol': symbol,
        'interval': interval,
        'limit': limit,
      },
    );
    final data = Map<String, dynamic>.from(response.data as Map);
    final candles = (data['candles'] as List<dynamic>? ?? const []);
    return candles
        .map((item) => MarketCandle.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }

  Future<List<dynamic>> getNews() async {
    final response = await _apiClient.get('/news');
    final data = response.data;
    if (data is Map) {
      final nestedData = data['data'];
      if (nestedData is Map && nestedData['items'] is List) {
        return List<dynamic>.from(nestedData['items'] as List);
      }
      if (data['items'] is List) {
        return List<dynamic>.from(data['items'] as List);
      }
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<List<dynamic>> getSignals() async {
    final response = await _apiClient.get('/signals');
    final data = response.data;
    if (data is Map && data['items'] is List) {
      return List<dynamic>.from(data['items'] as List);
    }
    if (data is Map && data['data'] is List) {
      return List<dynamic>.from(data['data'] as List);
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<List<dynamic>> getWhales() async {
    final response = await _apiClient.get('/whales');
    final data = response.data;
    if (data is Map && data['data'] is List) {
      return List<dynamic>.from(data['data'] as List);
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<List<dynamic>> getLiquidations() async {
    final response = await _apiClient.get('/liquidations');
    final data = response.data;
    if (data is Map && data['data'] is List) {
      return List<dynamic>.from(data['data'] as List);
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<List<dynamic>> getNotifications() async {
    final response = await _apiClient.get('/notifications');
    final data = response.data;
    if (data is Map && data['data'] is List) {
      return List<dynamic>.from(data['data'] as List);
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<List<dynamic>> getWatchlist() async {
    final response = await _apiClient.get('/watchlists');
    final data = response.data;
    if (data is Map && data['data'] is List) {
      return List<dynamic>.from(data['data'] as List);
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<List<dynamic>> getLessonProgress() async {
    final response = await _apiClient.get('/lessons/progress');
    final data = response.data;
    if (data is Map && data['data'] is List) {
      return List<dynamic>.from(data['data'] as List);
    }
    if (data is List) {
      return data;
    }
    return const [];
  }

  Future<Map<String, dynamic>> createSignal(Map<String, dynamic> payload) async {
    final response = await _apiClient.post('/signals', data: payload);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> createSignalSafe(Map<String, dynamic> payload) async {
    try {
      return await createSignal(payload);
    } catch (error) {
      return {
        'success': false,
        'ok': false,
        'message': error.toString(),
        'error': error.toString(),
      };
    }
  }

  Future<Map<String, dynamic>> updateSignal(String id, Map<String, dynamic> payload) async {
    final response = await _apiClient.patch('/signals/$id', data: payload);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> updateSignalSafe(String id, Map<String, dynamic> payload) async {
    try {
      return await updateSignal(id, payload);
    } catch (error) {
      return {
        'success': false,
        'ok': false,
        'message': error.toString(),
        'error': error.toString(),
      };
    }
  }

  Future<Map<String, dynamic>> sendChat(Map<String, dynamic> payload) async {
    final response = await _apiClient.post('/ai/chat', data: payload);
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> sendChatSafe(Map<String, dynamic> payload) async {
    try {
      return await sendChat(payload);
    } catch (error) {
      final message = error.toString();
      return {
        'reply':
            message.contains('401')
                ? 'You are not authenticated. Please sign in again so the AI can access the backend.'
                : message.contains('403')
                    ? 'Your account does not have permission to use this feature.'
                    : message.contains('503')
                        ? 'The backend market service is temporarily unavailable.'
                        : 'I could not reach the backend just now. Please check the FastAPI server and API_BASE_URL.',
        'mode': 'fallback',
        'error': message,
      };
    }
  }

  Future<Map<String, dynamic>> getScanner({
    required String symbol,
    String interval = '1h',
  }) async {
    final response = await _apiClient.get(
      '/scanner/symbol',
      queryParameters: {'symbol': symbol, 'interval': interval},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> getMultiTimeframeScanner({
    required String symbol,
    String intervals = '15m,1h,4h',
  }) async {
    final response = await _apiClient.get(
      '/scanner/mtf',
      queryParameters: {'symbol': symbol, 'intervals': intervals},
    );
    return Map<String, dynamic>.from(response.data as Map);
  }
}
