import 'package:trademind_ai/core/network/api_client.dart';

class DeviceService {
  DeviceService(this._apiClient);

  final ApiClient _apiClient;

  Future<void> registerFcmToken({
    required String token,
    required String platform,
  }) async {
    await _apiClient.post(
      '/devices/register',
      data: {
        'token': token,
        'platform': platform,
      },
    );
  }
}
