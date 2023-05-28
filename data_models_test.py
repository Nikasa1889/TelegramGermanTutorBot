from datetime import datetime
import unittest
from data_models import UserProfileDB, UserProfile, LearningSession


class TestUserProfileDB(unittest.IsolatedAsyncioTestCase):
  def setUp(self):
    self.user_profile_db = UserProfileDB()
    self.test_user_id = 999999999
    self.test_user_id2 = 999999998 

  async def asyncSetUp(self):
    # Clean up any previous test user data from the database
    await self.user_profile_db.remove_user_profile(self.test_user_id)
    await self.user_profile_db.remove_user_profile(self.test_user_id2)

  async def asyncTearDown(self):
    # Clean up the test user data from the database after running the tests
    await self.user_profile_db.remove_user_profile(self.test_user_id)
    await self.user_profile_db.remove_user_profile(self.test_user_id2)

  async def test_get_user_profile(self):
    user_profile = await self.user_profile_db.get_user_profile(self.test_user_id)
    self.assertEqual(user_profile.user_id, self.test_user_id)
    self.assertEqual(len(user_profile.sessions), 0)
    self.assertEqual(len(user_profile.vocabs.dictionary), 0)

  async def test_set_user_profile(self):
    user_profile = UserProfile(user_id=self.test_user_id)
    user_profile.sessions.append(
      LearningSession(session_id=1, chat_id="123456", 
                      text="test text", start_time=datetime.now()))
    await self.user_profile_db.set_user_profile(user_profile)

    retrieved_user_profile = await self.user_profile_db.get_user_profile(self.test_user_id)

    self.assertEqual(retrieved_user_profile.user_id, user_profile.user_id)
    self.assertEqual(len(retrieved_user_profile.sessions), 1)
    self.assertEqual(retrieved_user_profile.sessions[0].session_id, 1)

  async def test_get_all_user_profiles(self):
    # Create three test user profiles
    user_profile_1 = UserProfile(user_id=self.test_user_id)
    user_profile_2 = UserProfile(user_id=self.test_user_id2)

    # Save the test user profiles to the database
    await self.user_profile_db.set_user_profile(user_profile_1)
    await self.user_profile_db.set_user_profile(user_profile_2)

    # Retrieve all user profiles from the database
    all_user_profiles = await self.user_profile_db.get_all_user_profiles()

    # Ensure that the retrieved user profiles match the expected IDs
    retrieved_user_ids = [profile.user_id for profile in all_user_profiles]
    self.assertIn(user_profile_1.user_id, retrieved_user_ids)
    self.assertIn(user_profile_2.user_id, retrieved_user_ids)


if __name__ == '__main__':
    unittest.main()
